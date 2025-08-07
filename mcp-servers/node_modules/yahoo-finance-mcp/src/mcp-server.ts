#!/usr/bin/env node
/**
 * Yahoo Finance MCP Server - 入口文件
 * 使用新的YahooFinanceMcp类启动MCP服务器
 */
import { yahooFinanceMcp } from './server.js';

// 启动MCP服务器
async function main() {
  try {
    await yahooFinanceMcp.start();
  } catch (error) {
    console.error("Failed to start MCP server:", error);
    process.exit(1);
  }
}

// 启动服务
main().catch((error) => {
  console.error("Uncaught error:", error);
  process.exit(1);
});
