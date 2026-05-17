import React from 'react';
import { Link } from 'react-router-dom';

function HomePage() {
  return (
    <div className="home-page">
      <div className="home-content">
        <div className="home-header">
          <div className="home-logo">❄</div>
          <h1 className="home-title">Freezer Management System</h1>
          <p className="home-subtitle">Laboratory Sample Storage &amp; Tracking</p>
        </div>

        <div className="home-actions">
          <Link to="/introduction" className="home-action-btn">
            <span className="action-icon">⊕</span>
            <span className="action-label">Container Introduction</span>
            <span className="action-desc">Add new samples to the freezer</span>
          </Link>

          <Link to="/retrieval" className="home-action-btn">
            <span className="action-icon">⊖</span>
            <span className="action-label">Container Retrieval</span>
            <span className="action-desc">Remove containers from storage</span>
          </Link>

          <Link to="/lookup" className="home-action-btn">
            <span className="action-icon">◎</span>
            <span className="action-label">Lookup Container</span>
            <span className="action-desc">Find a container by barcode or batch</span>
          </Link>
        </div>

        <div className="home-admin-link">
          <Link to="/admin" className="admin-text-link">Admin Page →</Link>
        </div>
      </div>
    </div>
  );
}

export default HomePage;
