import { Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import DeadLettersPage from "./pages/DeadLettersPage";
import EndpointDetail from "./pages/EndpointDetail";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/endpoints/:id" element={<EndpointDetail />} />
      <Route path="/dead-letters" element={<DeadLettersPage />} />
    </Routes>
  );
}
