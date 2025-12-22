import React from 'react';

export default function StatusBanner({ health }) {
  if (!health || health.status === 'healthy') return null;

  return (
    <div style={{
      marginBottom: '20px',
      padding: '12px',
      backgroundColor: '#FEF7E0',
      border: '1px solid #FFE082',
      borderRadius: '4px',
      fontSize: '13px',
      color: '#B00020',
      display: 'flex',
      alignItems: 'center'
    }}>
      <span style={{ marginRight: '8px', fontSize: '16px' }}>⚠️</span>
      <span>
        Backend is <strong>{health ? 'reporting issues' : 'unreachable'}</strong>.
        Ensure <code>python main.py</code> or docker is running on port 8000.
      </span>
    </div>
  );
}
