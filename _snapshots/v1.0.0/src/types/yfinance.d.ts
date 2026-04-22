declare module "yahoo-finance2" {
  export interface QuoteResult {
    symbol?: string;
    regularMarketPrice?: number;
    navPrice?: number;
    currency?: string;
    quoteType?: string;
    longName?: string;
    shortName?: string;
    netExpenseRatio?: number;
    dividendYield?: number;
    totalAssets?: number;
    fundFamily?: string;
    category?: string;
    regularMarketChangePercent?: number;
    ytdReturn?: number;
    threeYearAverageReturn?: number;
    fiveYearAverageReturn?: number;
    beta3Year?: number;
    [key: string]: any;
  }

  export interface HistoryBar {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }

  export interface YahooFinanceOptions {
    suppressNotices?: string[];
  }

  export class YahooFinance {
    constructor(options?: YahooFinanceOptions);
    quote(symbol: string, queryOptions?: unknown): Promise<QuoteResult>;
    quoteSummary(symbol: string, queryOptions?: unknown): Promise<unknown>;
    historical(symbol: string, options?: { interval?: string; period?: string }): Promise<HistoryBar[]>;
  }

  export default YahooFinance;
}
