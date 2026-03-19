import { Routes, Route, NavLink, useNavigate } from "react-router-dom";
import ShiftList from "./pages/ShiftList";
import UploadShift from "./pages/UploadShift";
import ShiftDetail from "./pages/ShiftDetail";

export default function App() {
  return (
    <>
      <header className="app-header">
        <h1>✈ ATC Transcript Analyzer</h1>
        <nav>
          <NavLink to="/" end>
            <button className="btn btn-ghost btn-sm">Shifts</button>
          </NavLink>
          <NavLink to="/upload">
            <button className="btn btn-primary btn-sm">+ Upload Audio</button>
          </NavLink>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<ShiftList />} />
        <Route path="/upload" element={<UploadShift />} />
        <Route path="/shift/:shiftId" element={<ShiftDetail />} />
      </Routes>
    </>
  );
}
