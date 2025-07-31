import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Tabs, Tab } from '@/components/ui/tabs';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

const API_BASE = 'http://localhost:8000';
const API_KEY = 'your-secure-api-key'; // Replace with your actual key

export default function TradingDashboard() {
  const [positions, setPositions] = useState([]);
  const [config, setConfig] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [loading, setLoading] = useState(false);

  const fetchPositions = async () => {
    const res = await axios.get(`${API_BASE}/positions`, {
      headers: { Authorization: `Bearer ${API_KEY}` },
    });
    setPositions(res.data.positions);
  };

  const fetchConfig = async () => {
    const res = await axios.get(`${API_BASE}/config`, {
      headers: { Authorization: `Bearer ${API_KEY}` },
    });
    setConfig(res.data);
  };

  const updateConfig = async () => {
    await axios.post(`${API_BASE}/config`, config, {
      headers: { Authorization: `Bearer ${API_KEY}` },
    });
    alert('설정이 저장되었습니다.');
  };

  const triggerAnalysis = async (symbol) => {
    await axios.post(`${API_BASE}/force_analysis/${symbol}`, {}, {
      headers: { Authorization: `Bearer ${API_KEY}` },
    });
    alert(`${symbol} 분석 실행됨`);
  };

  const closePosition = async (symbol) => {
    await axios.post(`${API_BASE}/close_position/${symbol}`, {}, {
      headers: { Authorization: `Bearer ${API_KEY}` },
    });
    alert(`${symbol} 포지션 종료됨`);
  };

  useEffect(() => {
    fetchPositions();
    fetchConfig();
  }, []);

  if (!config) return <div className="p-4">설정을 불러오는 중...</div>;

  const chartData = Object.entries(config.leverage).map(([symbol, leverage]) => ({
    symbol,
    leverage
  }));

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="p-6">
      <Tab value="dashboard" label="📊 대시보드">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h2 className="text-xl font-bold mb-4">📊 현재 포지션</h2>
            {positions.map((pos) => (
              <Card key={pos.symbol} className="mb-4">
                <CardContent>
                  <div className="font-semibold text-lg">{pos.symbol}</div>
                  <div>방향: {pos.side}</div>
                  <div>수량: {pos.contracts}</div>
                  <div>진입가: ${pos.entry_price}</div>
                  <div>현재가: ${pos.current_price}</div>
                  <div>PnL: {pos.pnl.toFixed(2)} ({pos.pnl_percentage.toFixed(2)}%)</div>
                  <div className="mt-2 flex gap-2">
                    <Button onClick={() => triggerAnalysis(pos.symbol)}>즉시 분석</Button>
                    <Button variant="destructive" onClick={() => closePosition(pos.symbol)}>강제 종료</Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div>
            <h2 className="text-xl font-bold mb-4">⚙️ 설정 변경</h2>
            <div className="mb-4">
              <label className="font-medium">예측 임계값 (%)</label>
              <Input
                type="number"
                value={config.prediction_threshold * 100}
                onChange={(e) =>
                  setConfig({ ...config, prediction_threshold: e.target.value / 100 })
                }
              />
            </div>

            <div className="mb-4">
              <label className="font-medium">신뢰도 임계값 (%)</label>
              <Input
                type="number"
                value={config.confidence_threshold}
                onChange={(e) =>
                  setConfig({ ...config, confidence_threshold: parseFloat(e.target.value) })
                }
              />
            </div>

            <div className="mb-4">
              <label className="font-medium">진입비율 (% 자산)</label>
              <Slider
                defaultValue={[config.position_size_ratio * 100]}
                max={100}
                step={1}
                onValueChange={(val) =>
                  setConfig({ ...config, position_size_ratio: val[0] / 100 })
                }
              />
            </div>

            <div className="mb-4">
              <label className="font-medium">손절 (%)</label>
              <Input
                type="number"
                value={config.stop_loss.BTCUSDT * 100}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    stop_loss: {
                      ...config.stop_loss,
                      BTCUSDT: parseFloat(e.target.value) / 100,
                    },
                  })
                }
              />
            </div>

            <div className="mb-4">
              <label className="font-medium">익절 (%)</label>
              <Input
                type="number"
                value={config.take_profit.BTCUSDT * 100}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    take_profit: {
                      ...config.take_profit,
                      BTCUSDT: parseFloat(e.target.value) / 100,
                    },
                  })
                }
              />
            </div>

            <div className="mt-4">
              <Button onClick={updateConfig}>설정 저장</Button>
            </div>
          </div>
        </div>
      </Tab>

      <Tab value="leverage" label="📈 레버리지 시각화">
        <h2 className="text-xl font-bold mb-4">종목별 레버리지 현황</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <XAxis dataKey="symbol" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="leverage" fill="#8884d8" />
          </BarChart>
        </ResponsiveContainer>
      </Tab>

      <Tab value="logs" label="📜 전략 로그">
        <h2 className="text-xl font-bold">전략 로그 (준비 중)</h2>
        <p>최근 예측, 매매 기록, AI 판단 내역 등을 여기에 표시할 수 있습니다.</p>
      </Tab>
    </Tabs>
  );
}

