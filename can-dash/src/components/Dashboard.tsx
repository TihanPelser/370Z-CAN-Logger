import React from 'react';
import styled from 'styled-components';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

// Vehicle data interface
interface VehicleData {
  engineRpm: number;
  vehicleSpeed: number;
  coolantTemp: number;
  fuelLevel: number;
  engineLoad: { time: string; load: number }[];
  batteryVoltage: number;
}

interface DashboardProps {
  data: VehicleData;
}

const DashboardContainer = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: auto auto auto;
  gap: 20px;
  padding: 20px;
  flex: 1;
  
  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

const Card = styled.div`
  background-color: #212121;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
`;

const CardTitle = styled.h3`
  font-size: 1.2rem;
  margin-bottom: 15px;
  color: #ffffff;
  font-weight: normal;
`;

const ValueDisplay = styled.div`
  font-size: 3rem;
  font-weight: bold;
  margin-top: 10px;
`;

const Unit = styled.span`
  font-size: 1.2rem;
  opacity: 0.7;
  margin-left: 5px;
`;

const ProgressBar = styled.div<{ progress: number }>`
  width: 100%;
  height: 20px;
  background-color: #333;
  border-radius: 10px;
  overflow: hidden;
  margin-top: 20px;
  
  &::after {
    content: '';
    display: block;
    height: 100%;
    width: ${props => props.progress}%;
    background-color: #4CAF50;
    border-radius: 10px;
    transition: width 0.3s ease;
  }
`;

const NotificationArea = styled.div`
  grid-column: 1 / -1;
  background-color: #212121;
  border-radius: 8px;
  padding: 10px 20px;
  color: #fff;
`;

const StatusValue = styled.div<{ color?: string }>`
  font-size: 2.5rem;
  font-weight: bold;
  color: ${props => props.color || '#fff'};
  display: flex;
  justify-content: center;
  align-items: center;
`;

const WideCard = styled(Card)`
  grid-column: span 2;
  
  @media (max-width: 768px) {
    grid-column: span 1;
  }
`;

// Gauge component for RPM and Speed
const GaugeContainer = styled.div`
  position: relative;
  width: 200px;
  height: 100px;
  overflow: hidden;
  margin: 20px 0;
`;

const GaugeBackground = styled.div`
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: #333;
`;

const GaugeFill = styled.div<{ percent: number, color: string }>`
  position: absolute;
  top: 0;
  left: 0;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  clip-path: polygon(100px 100px, 100px 0, ${props => 100 + 100 * Math.sin(props.percent * Math.PI)}px ${props => 100 - 100 * Math.cos(props.percent * Math.PI)}px);
  background: ${props => props.color};
  transform-origin: center bottom;
`;

const GaugeNeedle = styled.div<{ rotation: number }>`
  position: absolute;
  top: 10px;
  left: 98px;
  width: 4px;
  height: 90px;
  background: #fff;
  transform: rotate(${props => props.rotation}deg);
  transform-origin: bottom center;
  border-radius: 2px;
  z-index: 10;
  transition: transform 0.5s ease;
`;

const GaugeCenter = styled.div`
  position: absolute;
  bottom: 0;
  left: 90px;
  width: 20px;
  height: 20px;
  background: #626262;
  border-radius: 50%;
  z-index: 20;
`;

const GaugeValue = styled.div`
  position: absolute;
  bottom: 30px;
  width: 100%;
  text-align: center;
  font-size: 2rem;
  font-weight: bold;
  color: #fff;
  z-index: 30;
`;

const Dashboard: React.FC<DashboardProps> = ({ data }) => {
  // Calculate gauge values
  const rpmPercent = Math.min(data.engineRpm / 8000, 1);
  const rpmRotation = -90 + (rpmPercent * 180);
  
  const speedPercent = Math.min(data.vehicleSpeed / 160, 1);
  const speedRotation = -90 + (speedPercent * 180);
  
  // Calculate gauge colors based on values
  const getRpmColor = (rpm: number) => {
    if (rpm > 7000) return '#ff4d4d'; // Red when near redline
    if (rpm > 5500) return '#ffa500'; // Orange when high
    return '#4CAF50'; // Green when normal
  };
  
  const getTempColor = (temp: number) => {
    if (temp > 220) return '#ff4d4d'; // Red when hot
    if (temp < 160) return '#3498db'; // Blue when cold
    return '#4CAF50'; // Green when normal
  };

  return (
    <DashboardContainer>
      {/* RPM Gauge */}
      <Card>
        <CardTitle>ENGINE RPM</CardTitle>
        <GaugeContainer>
          <GaugeBackground />
          <GaugeFill percent={rpmPercent} color={getRpmColor(data.engineRpm)} />
          <GaugeNeedle rotation={rpmRotation} />
          <GaugeCenter />
          <GaugeValue>{data.engineRpm}</GaugeValue>
        </GaugeContainer>
      </Card>

      {/* Speed Gauge */}
      <Card>
        <CardTitle>VEHICLE SPEED</CardTitle>
        <GaugeContainer>
          <GaugeBackground />
          <GaugeFill percent={speedPercent} color="#4CAF50" />
          <GaugeNeedle rotation={speedRotation} />
          <GaugeCenter />
          <GaugeValue>{data.vehicleSpeed}</GaugeValue>
        </GaugeContainer>
        <StatusValue>mph</StatusValue>
      </Card>

      {/* Coolant Temperature */}
      <Card>
        <CardTitle>COOLANT TEMP</CardTitle>
        <StatusValue color={getTempColor(data.coolantTemp)}>
          {data.coolantTemp}
          <Unit>°F</Unit>
        </StatusValue>
      </Card>

      {/* Fuel Level */}
      <Card>
        <CardTitle>FUEL LEVEL</CardTitle>
        <ProgressBar progress={data.fuelLevel} />
        <StatusValue>{Math.round(data.fuelLevel)}%</StatusValue>
      </Card>

      {/* Engine Load Graph */}
      <WideCard>
        <CardTitle>ENGINE LOAD</CardTitle>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart
            data={data.engineLoad}
            margin={{
              top: 10,
              right: 30,
              left: 0,
              bottom: 0,
            }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="time" stroke="#999" />
            <YAxis stroke="#999" />
            <Tooltip contentStyle={{ backgroundColor: '#333', borderColor: '#444', color: '#fff' }} />
            <Area type="monotone" dataKey="load" stroke="#8884d8" fill="#8884d8" />
          </AreaChart>
        </ResponsiveContainer>
      </WideCard>

      {/* Battery Voltage */}
      <Card>
        <CardTitle>BATTERY VOLTAGE</CardTitle>
        <StatusValue color={data.batteryVoltage >= 12.0 ? '#4CAF50' : '#ff4d4d'}>
          {data.batteryVoltage}
          <Unit>V</Unit>
        </StatusValue>
      </Card>

      {/* Notification/Alert Area */}
      <NotificationArea>
        <p>System Status: Normal</p>
      </NotificationArea>
    </DashboardContainer>
  );
};

export default Dashboard;