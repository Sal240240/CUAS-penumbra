import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Home } from "./pages/Home";
import { Architecture } from "./pages/Architecture";
import { Simulator } from "./pages/Simulator";
import { Coverage } from "./pages/Coverage";
import { Hardware } from "./pages/Hardware";
import { Evidence } from "./pages/Evidence";
import { Program } from "./pages/Program";
import { References } from "./pages/References";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="architecture" element={<Architecture />} />
        <Route path="simulator" element={<Simulator />} />
        <Route path="coverage" element={<Coverage />} />
        <Route path="hardware" element={<Hardware />} />
        <Route path="evidence" element={<Evidence />} />
        <Route path="program" element={<Program />} />
        <Route path="references" element={<References />} />
      </Route>
    </Routes>
  );
}
