import YahooFinance from "yahoo-finance2";
import { z } from "zod";

// Initialize the Yahoo Finance client
const yahooFinance = YahooFinance;
// Tool parameter schemas using Zod
export const getQuoteSchema = z.object({
  symbol: z.string().describe("Stock symbol (e.g., AAPL, GOOGL)"),
});

export const getHistoricalDataSchema = z.object({
  symbol: z.string().describe("Stock symbol"),
  period1: z.string().default("1y").describe("Start date (YYYY-MM-DD) or period like '1mo', '1y'"),
  period2: z.string().default("now").describe("End date (YYYY-MM-DD) or 'now'"),
  interval: z.string().default("1d").describe("Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)"),
});

export const searchSymbolsSchema = z.object({
  query: z.string().describe("Search query"),
});

export const getCompanyInfoSchema = z.object({
  symbol: z.string().describe("Stock symbol"),
});

export const getRecommendationsSchema = z.object({
  symbol: z.string().describe("Stock symbol"),
});

export const getTrendingSymbolsSchema = z.object({});

export const getMarketSummarySchema = z.object({});

export const getNewsSchema = z.object({
  query: z.string().describe("Search query for news"),
  newsCount: z.number().default(10).describe("Number of news articles to return"),
});

export const getOptionsSchema = z.object({
  symbol: z.string().describe("Stock symbol"),
  date: z.string().optional().describe("Expiration date for options (YYYY-MM-DD format)"),
  formatted: z.boolean().default(false).describe("Whether to format the data"),
});

export const getInsightsSchema = z.object({
  symbol: z.string().describe("Stock symbol"),
  reportsCount: z.number().default(5).describe("Number of reports to return"),
});

export const getDailyGainersSchema = z.object({
  count: z.number().default(10).describe("Number of gainers to return"),
});

export const getDailyLosersSchema = z.object({
  count: z.number().default(10).describe("Number of losers to return"),
});

export const getChartSchema = z.object({
  symbol: z.string().describe("Stock symbol"),
  period1: z.string().default("1mo").describe("Start date (YYYY-MM-DD) or period like '1mo', '1y'"),
  period2: z.string().default("now").describe("End date (YYYY-MM-DD) or 'now'"),
  interval: z.string().default("1d").describe("Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)"),
  events: z.string().default("div|split|earn").describe("Event types to return (div|split|earn)"),
});

export const getQuoteSummarySchema = z.object({
  symbol: z.string().describe("Stock symbol"),
  modules: z.array(z.string()).default(["summaryDetail", "financialData", "recommendationTrend", "defaultKeyStatistics"]).describe("List of modules to include"),
});

// Core tool functions
export async function getQuote(params: z.infer<typeof getQuoteSchema>): Promise<any> {
  const { symbol } = params;
  const quote = await yahooFinance.quote(symbol);
  return quote;
}

export async function getHistoricalData(params: z.infer<typeof getHistoricalDataSchema>): Promise<any> {
  const { symbol, period1 = "1y", period2 = "now", interval = "1d" } = params;
  
  // Parse period strings
  const parsePeriod = (period: string) => {
    if (period === "now") return new Date();
    if (period.match(/^\d{4}-\d{2}-\d{2}$/)) return new Date(period);
    return period;
  };
  
  const data = await yahooFinance.historical(symbol, {
    period1: parsePeriod(period1),
    period2: parsePeriod(period2),
    interval: interval as any,
  });
  
  return data;
}

export async function searchSymbols(params: z.infer<typeof searchSymbolsSchema>): Promise<any> {
  const { query } = params;
  const results = await yahooFinance.search(query);
  return results;
}

export async function getCompanyInfo(params: z.infer<typeof getCompanyInfoSchema>): Promise<any> {
  const { symbol } = params;
  const [quoteSummary, assetProfile] = await Promise.all([
    yahooFinance.quoteSummary(symbol, {
      modules: ["summaryDetail", "financialData", "defaultKeyStatistics"]
    }),
    yahooFinance.quoteSummary(symbol, {
      modules: ["assetProfile"]
    }).catch(() => null), // Some symbols might not have asset profile
  ]);
  
  const companyInfo = {
    quote: quoteSummary,
    profile: assetProfile,
  };
  
  return companyInfo;
}

export async function getRecommendations(params: z.infer<typeof getRecommendationsSchema>): Promise<any> {
  const { symbol } = params;
  const recommendations = await yahooFinance.recommendationsBySymbol(symbol);
  return recommendations;
}

export async function getTrendingSymbols(params: z.infer<typeof getTrendingSymbolsSchema>): Promise<any> {
  const trending = await yahooFinance.trendingSymbols("US");
  return trending;
}

export async function getMarketSummary(params: z.infer<typeof getMarketSummarySchema>): Promise<any> {
  // Get major indices
  const indices = ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX"];
  const quotes = await Promise.all(
    indices.map(symbol => yahooFinance.quote(symbol))
  );
  
  const marketSummary = {
    indices: quotes.map(quote => ({
      symbol: quote.symbol,
      shortName: quote.shortName,
      regularMarketPrice: quote.regularMarketPrice,
      regularMarketChange: quote.regularMarketChange,
      regularMarketChangePercent: quote.regularMarketChangePercent,
      regularMarketTime: quote.regularMarketTime,
    })),
    timestamp: new Date().toISOString(),
  };
  
  return marketSummary;
}

export async function getNews(params: z.infer<typeof getNewsSchema>): Promise<any> {
  const { query, newsCount = 10 } = params;
  
  const searchResults = await yahooFinance.search(query, {
    newsCount,
  });
  
  return searchResults.news;
}

export async function getOptions(params: z.infer<typeof getOptionsSchema>): Promise<any> {
  const { symbol, date, formatted = false } = params;
  
  const queryOptions: any = { formatted };
  if (date) {
    queryOptions.date = new Date(date);
  }
  
  const options = await yahooFinance.options(symbol, queryOptions);
  return options;
}

export async function getInsights(params: z.infer<typeof getInsightsSchema>): Promise<any> {
  const { symbol, reportsCount = 5 } = params;
  
  const insights = await yahooFinance.insights(symbol, {
    reportsCount,
  });
  
  return insights;
}

export async function getDailyGainers(params: z.infer<typeof getDailyGainersSchema>): Promise<any> {
  const { count = 10 } = params;
  
  try {
    // 使用 screener API 替代 dailyGainers，这是更稳定的方式
    const queryOptions = { 
      scrIds: "day_gainers" as const,
      count, 
      lang: "en-US", 
      region: "US" 
    };
    
    // 使用 yahooFinance.screener 方法，传入包含 scrIds 的查询选项
    const gainersResult = await yahooFinance.screener(queryOptions);
    
    // 返回处理后的数据，保持与原有格式兼容
    return {
      id: gainersResult.id,
      title: gainersResult.title || "Day Gainers",
      description: gainersResult.description || "Discover the equities with the greatest gains in the trading day.",
      count: gainersResult.count || 0,
      total: gainersResult.total || 0,
      start: gainersResult.start || 0,
      quotes: gainersResult.quotes || [],
      timestamp: new Date().toISOString()
    };
  } catch (error) {
    console.error("Error in getDailyGainers:", error);
    throw new Error(`获取每日涨幅股票数据时发生错误: ${error instanceof Error ? error.message : "未知错误"}`);
  }
}

export async function getDailyLosers(params: z.infer<typeof getDailyLosersSchema>): Promise<any> {
  const { count = 10 } = params;
  
  try {
    // 使用 screener API 替代 dailyLosers，这是更稳定的方式
    const queryOptions = { 
      scrIds: "day_losers" as const,
      count, 
      lang: "en-US", 
      region: "US" 
    };
    
    // 使用 yahooFinance.screener 方法，传入包含 scrIds 的查询选项
    const losersResult = await yahooFinance.screener(queryOptions);
    
    // 返回处理后的数据，保持与原有格式兼容
    return {
      id: losersResult.id,
      title: losersResult.title || "Day Losers",
      description: losersResult.description || "Discover the equities with the greatest losses in the trading day.",
      count: losersResult.count || 0,
      total: losersResult.total || 0,
      start: losersResult.start || 0,
      quotes: losersResult.quotes || [],
      timestamp: new Date().toISOString()
    };
  } catch (error) {
    console.error("Error in getDailyLosers:", error);
    throw new Error(`获取每日跌幅股票数据时发生错误: ${error instanceof Error ? error.message : "未知错误"}`);
  }
}

export async function getChart(params: z.infer<typeof getChartSchema>): Promise<any> {
  const { symbol, period1 = "1mo", period2 = "now", interval = "1d", events = "div|split|earn" } = params;
  
  try {
    // Parse period strings
    const parsePeriod = (period: string) => {
      if (period === "now") return new Date();
      if (period.match(/^\d{4}-\d{2}-\d{2}$/)) return new Date(period);
      return period;
    };
    
    const chart = await yahooFinance.chart(symbol, {
      period1: parsePeriod(period1),
      period2: parsePeriod(period2),
      interval: interval as any,
      events,
    });
    
    // 安全处理 chart 数据，确保可以序列化为 JSON
    const safeChart = JSON.parse(JSON.stringify(chart, (key, value) => {
      // 处理无法序列化的特殊对象，如日期等
      if (value instanceof Date) return value.toISOString();
      return value;
    }));
    
    return safeChart;
  } catch (error) {
    console.error("Error in get_chart:", error);
    throw new Error(`获取图表数据时发生错误: ${error instanceof Error ? error.message : "未知错误"}`);
  }
}

export async function getQuoteSummary(params: z.infer<typeof getQuoteSummarySchema>): Promise<any> {
  const { symbol, modules = ["summaryDetail", "financialData", "recommendationTrend", "defaultKeyStatistics"] } = params;
  
  try {
    const quoteSummary = await yahooFinance.quoteSummary(symbol, {
      modules: modules as any,
    });
    
    // 安全处理 quoteSummary 数据，确保可以序列化为 JSON
    const safeQuoteSummary = JSON.parse(JSON.stringify(quoteSummary, (key, value) => {
      // 处理无法序列化的特殊对象，如日期等
      if (value instanceof Date) return value.toISOString();
      return value;
    }));
    
    return safeQuoteSummary;
  } catch (error) {
    console.error("Error in get_quote_summary:", error);
    throw new Error(`获取股票摘要数据时发生错误: ${error instanceof Error ? error.message : "未知错误"}`);
  }
}
