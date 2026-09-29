<template>
	<Dialog v-model="isOpen" :options="{ title: __('Select Warehouse'), size: 'md' }">
		<template #body-content>
			<div class="py-2">
				<div v-if="item" class="flex items-center gap-3 mb-3">
					<div
						class="w-12 h-12 bg-gray-100 rounded flex items-center justify-center overflow-hidden flex-shrink-0"
					>
						<img
							v-if="item.image"
							:src="item.image"
							loading="lazy"
							:alt="item.item_name"
							class="w-full h-full object-cover"
						/>
						<svg
							v-else
							class="h-6 w-6 text-gray-400"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
							/>
						</svg>
					</div>
					<div class="flex-1 min-w-0 text-start">
						<h3 class="text-sm font-semibold text-gray-900 truncate">
							{{ item.item_name }}
						</h3>
						<p class="text-xs text-gray-500">{{ item.item_code }}</p>
					</div>
				</div>

				<p class="text-xs text-gray-600 mb-3 text-start">
					{{ __("This item is available in multiple warehouses. Pick one to sell from.") }}
				</p>

				<!-- Loading -->
				<div v-if="loading" class="flex justify-center items-center py-8">
					<div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
				</div>

				<!-- Error -->
				<div
					v-else-if="error"
					class="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 text-start"
				>
					{{ error }}
				</div>

				<!-- Warehouse Options -->
				<div v-else class="flex flex-col gap-2 max-h-[50vh] overflow-y-auto">
					<button
						v-for="option in options"
						:key="option.warehouse"
						type="button"
						:disabled="option.disabled"
						@click="select(option)"
						:class="[
							'w-full flex items-center justify-between gap-3 p-3 rounded-lg border text-start transition-all touch-manipulation',
							option.disabled
								? 'bg-gray-50 border-gray-200 opacity-60 cursor-not-allowed'
								: 'bg-white border-gray-200 hover:border-blue-400 hover:bg-blue-50 active:scale-[0.99] cursor-pointer',
						]"
					>
						<div class="min-w-0">
							<p class="text-sm font-semibold text-gray-900 truncate">
								{{ option.label }}
							</p>
							<p v-if="option.isDefault" class="text-[11px] text-blue-600 font-medium">
								{{ __("This POS warehouse") }}
							</p>
						</div>
						<div class="text-end flex-shrink-0">
							<p
								:class="[
									'text-sm font-bold',
									option.available > 0 ? 'text-green-700' : 'text-red-600',
								]"
							>
								{{ formatQty(option.available) }} {{ item?.stock_uom || "" }}
							</p>
							<!-- Tile items: same quantity in boxes + pieces -->
							<p
								v-if="option.breakdown"
								class="text-xs font-semibold text-amber-700"
							>
								= {{ option.breakdown }}
							</p>
							<p v-if="option.inCart > 0" class="text-[11px] text-gray-500">
								{{ __("{0} in cart", [formatQty(option.inCart)]) }}
							</p>
						</div>
					</button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
/**
 * Warehouse Picker Dialog
 *
 * Shown when an item has stock outside the POS profile warehouse, so the
 * cashier can choose which warehouse the cart line is fulfilled from.
 * Emits `warehouse-selected` with { warehouse, actual_qty } where actual_qty is
 * the warehouse's server stock (cart validation subtracts cart lines itself).
 */
import { computed, ref, watch } from "vue";
import { call, Dialog } from "frappe-ui";
import { __ } from "@/utils/translation";
import { usePOSCartStore } from "@/stores/posCart";
import { formatQty, getCountBreakdown, getItemUomOptions, isTileItem } from "@/utils/tileUom";

const props = defineProps({
	modelValue: Boolean,
	item: Object,
	company: String,
	// POS profile warehouse (listed first, always shown)
	defaultWarehouse: String,
	// [{ name, warehouse }] used for display labels
	warehouses: {
		type: Array,
		default: () => [],
	},
	// When true, warehouses without available stock can't be picked
	enforceStock: {
		type: Boolean,
		default: true,
	},
});

const emit = defineEmits(["update:modelValue", "warehouse-selected"]);

const cartStore = usePOSCartStore();

const isOpen = computed({
	get: () => props.modelValue,
	set: (val) => emit("update:modelValue", val),
});

const loading = ref(false);
const error = ref("");
const stockRows = ref([]); // [{ warehouse, warehouse_name, actual_qty }]

watch(
	() => props.modelValue,
	(open) => {
		if (open && props.item) loadAvailability();
	}
);

async function loadAvailability() {
	loading.value = true;
	error.value = "";
	stockRows.value = [];
	try {
		const response = await call("pos_next.api.items.get_item_warehouse_availability", {
			item_code: props.item.item_code,
			company: props.company,
		});
		stockRows.value = response?.message || response || [];
	} catch (err) {
		console.error("Error loading warehouse availability:", err);
		error.value = err.message || __("Failed to load warehouse availability");
	} finally {
		loading.value = false;
	}
}

// Quantity of this item already in the cart per warehouse (in stock UOM)
function getCartQty(warehouse) {
	return cartStore.invoiceItems
		.filter(
			(line) =>
				line.item_code === props.item?.item_code &&
				(line.warehouse || props.defaultWarehouse) === warehouse
		)
		.reduce((sum, line) => sum + (line.quantity || 0) * (line.conversion_factor || 1), 0);
}

// Tile items with more than one count UOM (e.g. Box + Piece) get a whole-unit breakdown
const tileUomOptions = computed(() => {
	if (!isTileItem(props.item)) return null;
	const uomOptions = getItemUomOptions(props.item);
	const countBreakdown = getCountBreakdown(0, uomOptions);
	return countBreakdown && countBreakdown.countOptions.length > 1 ? uomOptions : null;
});

function getBreakdown(stockQty) {
	if (!tileUomOptions.value) return null;
	const text = getCountBreakdown(stockQty, tileUomOptions.value)?.text;
	// Skip when it adds nothing, e.g. "4 Piece" for 4 Piece
	return text && text !== `${formatQty(stockQty)} ${props.item.stock_uom}` ? text : null;
}

function getLabel(warehouse, fallbackName) {
	const match = props.warehouses.find((w) => w.name === warehouse);
	return match?.warehouse || fallbackName || warehouse;
}

const options = computed(() => {
	const rows = [...stockRows.value];

	// Always offer the POS warehouse, even when it has no stock
	if (props.defaultWarehouse && !rows.some((r) => r.warehouse === props.defaultWarehouse)) {
		rows.push({ warehouse: props.defaultWarehouse, actual_qty: 0 });
	}

	return rows
		.map((row) => {
			const actualQty = Number(row.actual_qty) || 0;
			const inCart = getCartQty(row.warehouse);
			const available = actualQty - inCart;
			return {
				warehouse: row.warehouse,
				label: getLabel(row.warehouse, row.warehouse_name),
				actualQty,
				inCart,
				available,
				breakdown: getBreakdown(available),
				isDefault: row.warehouse === props.defaultWarehouse,
				disabled: props.enforceStock && available <= 0,
			};
		})
		.sort((a, b) => (b.isDefault ? 1 : 0) - (a.isDefault ? 1 : 0) || b.available - a.available);
});

function select(option) {
	if (option.disabled) return;
	emit("warehouse-selected", { warehouse: option.warehouse, actual_qty: option.actualQty });
	isOpen.value = false;
}
</script>
