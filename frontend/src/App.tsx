import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { WordflowPage } from './pages';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<WordflowPage />} />
      <Route path="*" element={<WordflowPage />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
