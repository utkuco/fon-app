// Shared config for TYPE_LABELS, TYPE_COLORS, ASSET_COLORS, ASSET_LABELS
// Used across page.tsx, fund/[code]/page.tsx, and other components

export const TYPE_LABELS: Record<string, string> = {
  "VFF":   "Değişken",
  "SRF":   "Serbest",
  "OKS":   "Karma",
  "KFF":   "Tahvil & Bono",
  "DÖVİZ":"Döviz",
  "ALTIN": "Altın",
  "HİSSE": "Hisse",
  "BYF":   "Borsa Yönetilen",
  "YAT":   "Yatırım",
  "EMK":   "Emeklilik",
  "YF":    "Yabancı",
  "YYF":   "Yabancı Tahvil",
};

export const TYPE_COLORS: Record<string, string> = {
  "VFF": "bg-violet-100 text-violet-700",
  "OKS": "bg-blue-100 text-blue-700",
  "KFF": "bg-amber-100 text-amber-700",
  "SRF": "bg-green-100 text-green-700",
  "DÖVİZ": "bg-orange-100 text-orange-700",
  "ALTIN": "bg-yellow-100 text-yellow-700",
  "HİSSE": "bg-red-100 text-red-700",
  "BYF": "bg-purple-100 text-purple-700",
  "YAT": "bg-teal-100 text-teal-700",
  "EMK": "bg-pink-100 text-pink-700",
  "YF": "bg-indigo-100 text-indigo-700",
  "YYF": "bg-cyan-100 text-cyan-700",
};

export const ASSET_LABELS: Record<string, string> = {
  stock: "Hisse",
  government_bond: "Devlet Tahvili",
  private_sector_bond: "Özel Sektör",
  eurobond: "Eurobond",
  gold: "Altın",
  repo: "Repo",
  reverse_repo: "Ters Repo",
  treasury_bill: "Hazine Bonosu",
  bank_bills: "Banka Bonosu",
  commercial_paper: "Finansman Bonosu",
  term_deposit: "Vadeli Mevduat",
  etf: "BYF",
  derivatives: "Türev",
  foreign_equity: "Yabancı Hisse",
  foreign_bond: "Yabancı Tahvil",
  precious_metals: "Kıymetli Maden",
  participation_account: "Katılma",
  other: "Diğer",
};

export const ASSET_COLORS: Record<string, string> = {
  stock: "bg-blue-500",
  government_bond: "bg-amber-500",
  private_sector_bond: "bg-orange-400",
  eurobond: "bg-purple-500",
  gold: "bg-yellow-400",
  repo: "bg-green-400",
  reverse_repo: "bg-green-300",
  treasury_bill: "bg-amber-300",
  bank_bills: "bg-orange-300",
  commercial_paper: "bg-rose-300",
  term_deposit: "bg-teal-400",
  etf: "bg-violet-400",
  derivatives: "bg-pink-400",
  foreign_equity: "bg-indigo-400",
  foreign_bond: "bg-violet-300",
  precious_metals: "bg-yellow-300",
  participation_account: "bg-emerald-300",
  other: "bg-gray-400",
};
