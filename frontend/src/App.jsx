import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import './styles.css';

import HomePage                  from './pages/HomePage';
import ContainerIntroductionPage from './pages/ContainerIntroductionPage';
import LookupPage                from './pages/LookupPage';
import RetrievalPage             from './pages/RetrievalPage';
import AddFreezerPage, { AdminPage } from './pages/AddFreezerPage';

function PlaceholderPage({ title }) {
  return (
    <div className="placeholder-page">
      <h2>{title}</h2>
      <p>This page is not yet implemented.</p>
      <a href="/" className="admin-text-link">← Back to Home</a>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"                  element={<HomePage />} />
        <Route path="/introduction"      element={<ContainerIntroductionPage />} />
        <Route path="/retrieval"         element={<RetrievalPage />} />
        <Route path="/lookup"            element={<LookupPage />} />
        <Route path="/admin"             element={<AdminPage />} />
        <Route path="/admin/add-freezer" element={<AddFreezerPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;