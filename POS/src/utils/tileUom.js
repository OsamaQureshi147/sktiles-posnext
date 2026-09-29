/**
 * Tile UOM helpers - shared by the item card, UOM selection dialog and
 * warehouse picker so conversions and rounding stay consistent.
 *
 * Conversion factors are relative to the stock UOM (stock UOM = 1).
 */

// Item groups that get UOM prices / conversion breakdowns (compared case-insensitively)
export const TILE_ITEM_GROUPS = ["tile"];

export function isTileItem(item) {
	return TILE_ITEM_GROUPS.includes((item?.item_group || "").trim().toLowerCase());
}

// UOM names treated as area units (normalized: lowercase, alphanumerics only)
const AREA_UOM_NAMES = [
	"sqm",
	"sqmeter",
	"sqmeters",
	"sqmtr",
	"squaremeter",
	"squaremeters",
	"squaremetre",
	"squaremetres",
	"m2",
	"sqft",
	"squarefoot",
	"squarefeet",
];

export function isAreaUom(uom) {
	return AREA_UOM_NAMES.includes((uom || "").toLowerCase().replace(/[^a-z0-9]/g, ""));
}

// Avoid floating point noise (e.g. 3.0000000004) before ceil/floor
export function roundPrecise(value) {
	return Math.round(value * 1e6) / 1e6;
}

export function formatQty(value) {
	return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 3 });
}

/**
 * All UOMs of an item as [{ uom, conversion_factor }], stock UOM first.
 */
export function getItemUomOptions(item) {
	if (!item) return [];
	return [{ uom: item.stock_uom, conversion_factor: 1 }, ...(item.item_uoms || [])];
}

/**
 * Whole-unit breakdown of a stock quantity over the count UOMs (Box, Piece, ...),
 * largest first, with the smallest count unit rounded up (Math.ceil).
 *   e.g. 70 Piece (Box = 11 Piece) -> "6 Box + 4 Piece"
 *
 * @param {number} stockQty - Quantity in stock UOM
 * @param {Array} uomOptions - [{ uom, conversion_factor }]
 * @returns {{ text: string, references: string[], countOptions: Array, smallest: Object }|null}
 *          null when the item has no count UOMs
 */
export function getCountBreakdown(stockQty, uomOptions) {
	const countOptions = (uomOptions || [])
		.filter((opt) => opt.conversion_factor > 0 && !isAreaUom(opt.uom))
		.sort((a, b) => b.conversion_factor - a.conversion_factor);
	if (countOptions.length === 0) return null;

	const smallest = countOptions[countOptions.length - 1];
	let remaining = Math.ceil(roundPrecise(Math.abs(stockQty) / smallest.conversion_factor));

	const parts = [];
	const references = [];
	countOptions.forEach((opt, index) => {
		const perUnit = Math.max(1, Math.round(opt.conversion_factor / smallest.conversion_factor));
		const isLast = index === countOptions.length - 1;
		const count = isLast ? remaining : Math.floor(remaining / perUnit);
		remaining -= count * perUnit;
		if (count > 0) parts.push(`${count} ${opt.uom}`);

		if (!isLast) {
			references.push(`1 ${opt.uom} = ${formatQty(perUnit)} ${smallest.uom}`);
		}
	});

	let text = parts.length > 0 ? parts.join(" + ") : `0 ${smallest.uom}`;
	if (stockQty < 0 && parts.length > 0) text = parts.length > 1 ? `-(${text})` : `-${text}`;
	return { text, references, countOptions, smallest };
}
