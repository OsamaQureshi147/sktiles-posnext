<template>
	<p v-if="balance" class="font-semibold truncate" :class="colorClass">
		<template v-if="balance.net_balance > 0">
			{{ __("Outstanding") }}: {{ formatCurrency(balance.net_balance) }}
		</template>
		<template v-else-if="balance.net_balance < 0">
			{{ __("Credit") }}: {{ formatCurrency(-balance.net_balance) }}
		</template>
		<template v-else>{{ __("No outstanding balance") }}</template>
	</p>
</template>

<script setup>
/**
 * Customer receivable balance line (net of return / advance credit).
 * Re-fetches when the customer changes and whenever the cart store signals
 * that a sale or return changed balances (posCart.refreshCustomerBalance).
 *
 * @endpoint pos_next.api.credit_sales.get_customer_balance
 */
import { usePOSCartStore } from "@/stores/posCart";
import { call } from "@/utils/apiWrapper";
import { DEFAULT_CURRENCY, formatCurrency as formatCurrencyUtil } from "@/utils/currency";
import { logger } from "@/utils/logger";
import { isOffline } from "@/utils/offline";
import { computed, ref, watch } from "vue";

const log = logger.create("CustomerBalance");

const props = defineProps({
	customer: { type: String, default: null },
	company: { type: String, default: null },
	currency: { type: String, default: DEFAULT_CURRENCY },
});

const cartStore = usePOSCartStore();
const balance = ref(null);
let requestId = 0;

const colorClass = computed(() => {
	if (balance.value?.net_balance > 0) return "text-red-600";
	if (balance.value?.net_balance < 0) return "text-green-600";
	return "text-gray-500";
});

function formatCurrency(amount) {
	return formatCurrencyUtil(Number.parseFloat(amount || 0), props.currency);
}

async function load() {
	const id = ++requestId;
	if (!props.customer || isOffline()) {
		balance.value = null;
		return;
	}

	try {
		const data = await call("pos_next.api.credit_sales.get_customer_balance", {
			customer: props.customer,
			company: props.company,
		});
		// A newer request (customer switch / refresh) supersedes this one
		if (id === requestId) balance.value = data || null;
	} catch (error) {
		log.error("Error loading customer balance:", error);
		if (id === requestId) balance.value = null;
	}
}

watch(
	() => [props.customer, props.company],
	() => {
		balance.value = null; // don't show the previous customer's balance
		load();
	},
	{ immediate: true }
);

// Sale submitted or return created — balance changed on the server
watch(() => cartStore.customerBalanceVersion, load);
</script>
