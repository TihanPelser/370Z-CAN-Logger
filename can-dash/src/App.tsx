import { useState, useEffect } from "react";
import styled from "styled-components";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";
import Dashboard from "./components/Dashboard";

// Interface for vehicle data from backend
interface VehicleDataResponse {
  engine_rpm: number;
  vehicle_speed: number;
  coolant_temp: number;
  fuel_level: number;
  engine_load: EngineLoadData[];
  battery_voltage: number;
}

interface EngineLoadData {
  time: string;
  load: number;
}

// Transform data for use in our frontend
interface VehicleData {
  engineRpm: number;
  vehicleSpeed: number;
  coolantTemp: number;
  fuelLevel: number;
  engineLoad: { time: string; load: number }[];
  batteryVoltage: number;
}

const AppContainer = styled.div`
  height: 100vh;
  width: 100%;
  background-color: #1a1a1a;
  color: #ffffff;
  display: flex;
  flex-direction: column;
`;

const NavBar = styled.nav`
  display: flex;
  background-color: #191919;
  padding: 0.5rem;
  border-bottom: 1px solid #333;
`;

const NavItem = styled.div<{ active?: boolean }>`
  padding: 0.5rem 1.5rem;
  margin: 0 0.5rem;
  cursor: pointer;
  ${props => props.active && `
    border-bottom: 2px solid #fff;
    font-weight: bold;
  `}
`;

const StatusBar = styled.div`
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background-color: #222;
  font-size: 0.9rem;
`;

const StatusItem = styled.div<{ status?: 'connected' | 'disconnected' }>`
  display: flex;
  align-items: center;
  
  &::before {
    content: '';
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    background-color: ${props => props.status === 'connected' ? '#4CAF50' : '#ff4d4d'};
  }
`;

// Mock data for development - will be replaced with actual CAN bus data
const mockData: VehicleData = {
  engineRpm: 2500,
  vehicleSpeed: 45,
  coolantTemp: 195,
  fuelLevel: 65,
  engineLoad: [
    { time: '00:00', load: 35 },
    { time: '00:01', load: 45 },
    { time: '00:02', load: 30 },
    { time: '00:03', load: 60 },
    { time: '00:04', load: 40 },
    { time: '00:05', load: 50 },
    { time: '00:06', load: 55 },
    { time: '00:07', load: 45 },
    { time: '00:08', load: 65 },
  ],
  batteryVoltage: 12.5
};

function App() {
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [vehicleData, setVehicleData] = useState<VehicleData>(mockData);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Function to start CAN bus logging
  const startCanLogging = async () => {
    try {
      // In development without real backend commands, just simulate connection
      console.log("Connecting to CAN bus...");
      setIsConnected(true);
      setError(null);
      
      // Uncomment when backend is ready:
      // const result = await invoke<string>("start_can_logging");
      // console.log(result);
      // setIsConnected(true);
      // setError(null);
    } catch (e) {
      console.error("Failed to start CAN logging:", e);
      setError(String(e));
    }
  };
  
  // Function to stop CAN bus logging
  const stopCanLogging = async () => {
    try {
      // In development without real backend commands, just simulate disconnection
      console.log("Disconnecting from CAN bus...");
      setIsConnected(false);
      
      // Uncomment when backend is ready:
      // const result = await invoke<string>("stop_can_logging");
      // console.log(result);
      // setIsConnected(false);
    } catch (e) {
      console.error("Failed to stop CAN logging:", e);
      setError(String(e));
    }
  };

  // Auto-connect on startup
  useEffect(() => {
    startCanLogging();
    
    return () => {
      // Disconnect when component unmounts
      stopCanLogging();
    };
  }, []);
  
  // Fetch data at regular intervals (simulated for now)
  useEffect(() => {
    if (!isConnected) return;
    
    const interval = setInterval(() => {
      // Simulate data updates for development
      setVehicleData(prevData => ({
        ...prevData,
        engineRpm: Math.floor(Math.random() * 3000) + 1000,
        vehicleSpeed: Math.floor(Math.random() * 80) + 10,
        coolantTemp: Math.floor(Math.random() * 20) + 185,
        fuelLevel: prevData.fuelLevel > 0 ? prevData.fuelLevel - 0.1 : 100,
        engineLoad: [
          ...prevData.engineLoad.slice(1),
          { time: new Date().toLocaleTimeString('en-US', { hour12: false, 
                                                          hour: '2-digit', 
                                                          minute: '2-digit', 
                                                          second: '2-digit' }), 
            load: Math.floor(Math.random() * 50) + 30 }
        ],
        batteryVoltage: parseFloat((Math.random() * 0.2 + 12.4).toFixed(1))
      }));
      
      // When backend is ready, uncomment this to get real data:
      /*
      try {
        const data = await invoke<VehicleDataResponse>("get_vehicle_data");
        
        // Transform data to match our frontend structure
        setVehicleData({
          engineRpm: data.engine_rpm,
          vehicleSpeed: data.vehicle_speed,
          coolantTemp: data.coolant_temp,
          fuelLevel: data.fuel_level,
          engineLoad: data.engine_load.map(item => ({
            time: item.time,
            load: item.load
          })),
          batteryVoltage: data.battery_voltage
        });
        
        setError(null);
      } catch (e) {
        console.error("Failed to fetch vehicle data:", e);
        setError(String(e));
      }
      */
    }, 1000);
    
    return () => clearInterval(interval);
  }, [isConnected]);

  return (
    <AppContainer>
      <NavBar>
        <NavItem active={activeTab === "Dashboard"} onClick={() => setActiveTab("Dashboard")}>Dashboard</NavItem>
        <NavItem active={activeTab === "Diagnostics"} onClick={() => setActiveTab("Diagnostics")}>Diagnostics</NavItem>
        <NavItem active={activeTab === "Trends"} onClick={() => setActiveTab("Trends")}>Trends</NavItem>
        <NavItem active={activeTab === "Settings"} onClick={() => setActiveTab("Settings")}>Settings</NavItem>
      </NavBar>
      
      <StatusBar>
        <StatusItem status={isConnected ? 'connected' : 'disconnected'}>
          CAN Bus: {isConnected ? 'Connected' : 'Disconnected'}
        </StatusItem>
        {error && <div style={{ color: '#ff4d4d' }}>Error: {error}</div>}
      </StatusBar>
      
      {activeTab === "Dashboard" && <Dashboard data={vehicleData} />}
      {/* Other tabs would go here */}
    </AppContainer>
  );
}

export default App;
