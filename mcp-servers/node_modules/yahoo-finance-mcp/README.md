# Yahoo Finance MCP - Multi-Usage Library

[![npm version](https://badge.fury.io/js/yahoo-finance-mcp.svg)](https://badge.fury.io/js/yahoo-finance-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A versatile Yahoo Finance library that supports Model Context Protocol (MCP) servers. Provides comprehensive financial data access through multiple usage patterns.

## Features

- 🔌 **MCP Server**: Run as a standalone Model Context Protocol server
- 📚 **Direct Usage**: Import and use core functions directly
- 🌐 **Comprehensive API**: 14 financial data tools covering quotes, historical data, news, and more
- 📈 **Real-time stock quotes** and historical data
- 📰 **Financial news** and market updates  
- 📊 **Company information** and financial metrics
- 🔍 **Symbol search** and lookup functionality
- 📋 **Market summaries** and major indices
- 🎯 **Trending symbols** by region
- 📈 **Analyst recommendations** and ratings
- 🌐 **Multi-region support** (US, GB, CA, etc.)

## Table of Contents

- [Installation](#installation)
- [Usage Options](#usage-options)
- [Transport Modes](#transport-modes)
- [Available Tools](#available-tools)
- [Tool Categories](#tool-categories)
- [Examples](#examples)
- [API Reference](#api-reference)
- [Development](#development)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [License](#license)

## Installation

### Method 1: Install from npm (Recommended)

```bash
npm install -g yahoo-finance-mcp
```

### Method 2: Install for library usage

```bash
npm install yahoo-finance-mcp
```

### Method 3: Build from source

1. Clone the repository:
```bash
git clone https://github.com/phields/yahoo-finance-mcp.git
cd yahoo-finance-mcp
```

2. Install dependencies:
```bash
npm install
```

3. Build the project:
```bash
npm run build
```

## Usage Options

This library supports two different usage patterns:

### 1. As an MCP Server

#### With Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "npx",
      "args": ["yahoo-finance-mcp"]
    }
  }
}
```

#### Standalone Server

```bash
npm start
# or for global installation
yahoo-finance-mcp
```


### 2. Direct Function Usage

```typescript
import { getQuote, getHistoricalData, searchSymbols } from 'yahoo-finance-mcp/tools';

// Get current quote
const quote = await getQuote({ symbol: 'AAPL' });

// Get historical data
const history = await getHistoricalData({
  symbol: 'AAPL',
  period1: '2023-01-01',
  period2: '2023-12-31',
  interval: '1d'
});

// Search for symbols
const results = await searchSymbols({ query: 'Apple' });
```

## Transport Modes

The MCP server supports multiple transport modes for different use cases:

### 1. STDIO Transport (Default)
The most basic transport mode, suitable for command-line tools and direct process communication.

```typescript
import { yahooFinanceMcp } from "yahoo-finance-mcp/server";

// Start stdio transport (default)
await yahooFinanceMcp.start();

// Or explicitly specify
await yahooFinanceMcp.start('stdio');
```

### 2. SSE (Server-Sent Events) Transport
Suitable for web applications that support real-time data streaming.

```typescript
import { yahooFinanceMcp } from "yahoo-finance-mcp/server";

// Requires HTTP response object
await yahooFinanceMcp.start('sse', {
  endpoint: "/message",
  response: httpResponse // HTTP response object
});
```

#### Complete Example with Hono Framework

```typescript
import { Hono } from "hono";
import { yahooFinanceMcp } from "yahoo-finance-mcp/server";

const app = new Hono();

app.post("/mcp", async (c) => {
  await yahooFinanceMcp.start('sse', {
    endpoint: "/mcp",
    response: c.res
  });
  
  return c.text("Yahoo Finance MCP SSE server started");
});

export default app;
```

### 3. StreamableHTTP Transport
Suitable for HTTP scenarios that require session management.

```typescript
import { yahooFinanceMcp } from "yahoo-finance-mcp/server";

await yahooFinanceMcp.start('streamableHttp', {
  sessionIdGenerator: () => {
    return `yahoo-finance-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
});
```

### Advanced Usage

#### Get Server Instance
For custom integration and advanced configuration.

```typescript
const server = yahooFinanceMcp.getServer();
// Now you can use server for custom configuration
```

#### Create Custom Transports
Manually create transport instances for reuse.

```typescript
// Create SSE transport
const sseTransport = yahooFinanceMcp.createSSETransport("/custom-endpoint", response);

// Create StreamableHTTP transport
const httpTransport = yahooFinanceMcp.createStreamableHTTPTransport({
  sessionIdGenerator: () => `custom-session-${Date.now()}`
});
```

#### Environment Variable Configuration
Support for selecting transport type via environment variables.

```bash
# Set transport type
export TRANSPORT_TYPE=stdio        # Default
export TRANSPORT_TYPE=sse          # SSE transport
export TRANSPORT_TYPE=streamableHttp # HTTP transport

# Run server
npm start
```

#### Stop Server

```typescript
await yahooFinanceMcp.stop();
```

## Available Tools

This library provides 14 comprehensive financial data tools:

| Tool | Description | Parameters |
|------|-------------|------------|
| `getQuote` | Get current stock quote | `symbol` |
| `getHistoricalData` | Get historical price data | `symbol`, `period1`, `period2`, `interval` |
| `searchSymbols` | Search for stock symbols | `query` |
| `getCompanyInfo` | Get company profile information | `symbol` |
| `getRecommendations` | Get analyst recommendations | `symbol` |
| `getTrendingSymbols` | Get trending stocks by region | - |
| `getMarketSummary` | Get major market indices | - |
| `getNews` | Get financial news | `query`, `newsCount` |
| `getOptions` | Get options data | `symbol`, `formatted`, `date?` |
| `getInsights` | Get research insights | `symbol`, `reportsCount` |
| `getDailyGainers` | Get top gaining stocks | - |
| `getDailyLosers` | Get top losing stocks | - |
| `getChart` | Get chart data | `symbol`, `range`, `interval` |
| `getQuoteSummary` | Get comprehensive quote data | `symbol`, `modules` |

## Tool Categories

### Quoting Tools
Core stock price and quote functionality:
- `getQuote` - Current stock quotes
- `getHistoricalData` - Historical price data 
- `getChart` - Chart data for visualization
- `getQuoteSummary` - Comprehensive quote information

### Analysis Tools  
Market analysis and research:
- `getRecommendations` - Analyst recommendations
- `getInsights` - Research reports and analysis
- `getOptions` - Options chain data
- `getCompanyInfo` - Company profile and financial metrics

### Discovery Tools
Finding and exploring stocks:
- `searchSymbols` - Symbol and company search
- `getTrendingSymbols` - Popular/trending stocks
- `getDailyGainers` - Best performing stocks
- `getDailyLosers` - Worst performing stocks

### Market Data Tools
Overall market information:
- `getMarketSummary` - Major indices and market overview
- `getNews` - Financial news and updates

## Examples

```
┌─────────────────────────────────────┐
│           Usage Layers              │
├─────────────────────────────────────┤
│   MCP Server   │    Direct Usage    │
│    (mcp.ts)    │                    │
├─────────────────────────────────────┤
│         Core Business Logic         │
│            (tools.ts)               │
├─────────────────────────────────────┤
│        Yahoo Finance API            │
│      (yahoo-finance2 library)       │
└─────────────────────────────────────┘
```

### Key Benefits

- **Type Safety**: Full TypeScript support with Zod schema validation
- **Modularity**: Use only what you need 
- **Flexibility**: Multiple integration patterns
- **Consistency**: Same core functions across all usage patterns
- **Extensibility**: Easy to add new tools or modify existing ones

## Development

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Setup

```bash
git clone https://github.com/phields/yahoo-finance-mcp.git
cd yahoo-finance-mcp
npm install
```

### Development Commands

```bash
# Build the project
npm run build

# Start MCP server in development
npm run dev

# Start MCP server 
npm start

# Run tests (if available)
npm test

# Clean build artifacts
npm run clean
```

### Adding New Tools

1. Add your function to `src/tools.ts` with Zod schema
2. Export the function and schema
3. Add MCP handler to `src/mcp-server.ts`
4. Update exports in `src/index.ts`

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-tool`
3. Make your changes
4. Test your changes: `npm run build && npm test`
5. Commit your changes: `git commit -am 'Add new tool'`
6. Push to the branch: `git push origin feature/new-tool`
7. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Acknowledgments

- Built on top of the excellent [yahoo-finance2](https://github.com/gadicc/node-yahoo-finance2) library
- Inspired by the [Model Context Protocol](https://modelcontextprotocol.io/) specification

## Support

- 📖 [Documentation](https://github.com/phields/yahoo-finance-mcp#readme)
- 🐛 [Issue Tracker](https://github.com/phields/yahoo-finance-mcp/issues)
- 💬 [Discussions](https://github.com/phields/yahoo-finance-mcp/discussions)

---

**Note**: This library provides access to Yahoo Finance data for educational and research purposes. Please respect Yahoo Finance's terms of service and rate limits when using this library in production applications.

### Key Benefits

- **Type Safety**: Full TypeScript support with Zod schema validation
- **Modularity**: Use only what you need 
- **Flexibility**: Multiple integration patterns
- **Consistency**: Same core functions across all usage patterns
- **Extensibility**: Easy to add new tools or modify existing ones

## Error Handling

The server includes comprehensive error handling for:
- Invalid stock symbols
- API rate limiting
- Network timeouts
- Market closure periods
- Invalid date ranges

## Rate Limiting

This server respects Yahoo Finance's rate limits and implements:
- Request throttling
- Automatic retry with exponential backoff
- Graceful degradation during high load periods

## Development

### Prerequisites

- Node.js 18.x or higher
- npm or yarn package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/phields/yahoo-finance-mcp.git
cd yahoo-finance-mcp
```

2. Install dependencies:
```bash
npm install
```

3. Start development server:
```bash
npm run dev
```

### Scripts

- `npm run build` - Build the TypeScript project
- `npm run dev` - Start development server with hot reload
- `npm start` - Start production server
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix linting issues automatically

### Project Structure

```
yahoo-finance-mcp/
├── src/
│   └── index.ts          # Main server implementation
├── build/                # Compiled JavaScript output
├── tests/                # Test files
├── package.json          # Dependencies and scripts
├── tsconfig.json         # TypeScript configuration
└── README.md            # This file
```

### Testing

```bash
# Run tests
npm test

# Run tests with coverage
npm run test:coverage
```

### Linting

```bash
npm run lint
npm run lint:fix
```

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass (`npm test`)
6. Run linting (`npm run lint`)
7. Commit your changes (`git commit -m 'Add some amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

### Contribution Guidelines

- Follow the existing code style
- Add tests for new features
- Update documentation as needed
- Ensure all CI checks pass

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes.

## Support

- 🐛 **Bug reports**: [GitHub Issues](https://github.com/phields/yahoo-finance-mcp/issues)
- 💡 **Feature requests**: [GitHub Issues](https://github.com/phields/yahoo-finance-mcp/issues)
- 💬 **Questions**: [GitHub Discussions](https://github.com/phields/yahoo-finance-mcp/discussions)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Disclaimer

⚠️ **Important**: This project is for educational and informational purposes only. It is not intended for financial advice or trading recommendations. Always conduct your own research and consult with qualified financial professionals before making investment decisions.

The data provided by this server is sourced from Yahoo Finance and may be subject to delays, inaccuracies, or interruptions. Use at your own risk.

## Acknowledgments

- [Yahoo Finance](https://finance.yahoo.com/) for providing the financial data
- [Model Context Protocol](https://modelcontextprotocol.io/) for the MCP specification
- [yahoo-finance2](https://github.com/gadicc/node-yahoo-finance2) for the Yahoo Finance API wrapper
