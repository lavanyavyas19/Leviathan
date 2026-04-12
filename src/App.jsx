import React, { useState, useEffect } from 'react';
import { getCurrentUser, signOut } from 'aws-amplify/auth';
import LoginPage from './components/LoginPage';
import Dashboard from './components/Dashboard';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [hasStaleSession, setHasStaleSession] = useState(false);

  // Check for existing Cognito session on app load
  useEffect(() => {
    const checkAuthSession = async () => {
      try {
        await getCurrentUser();
        // User is already authenticated in Cognito
        setIsAuthenticated(true);
        setHasStaleSession(false);
      } catch (err) {
        // No existing session or session is invalid
        setIsAuthenticated(false);
        setHasStaleSession(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuthSession();
  }, []);

  const handleLogin = () => {
    setIsAuthenticated(true);
    setHasStaleSession(false);
  };

  const handleLogout = async () => {
    try {
      await signOut();
    } catch (err) {
      console.error('Sign out error:', err);
    } finally {
      setIsAuthenticated(false);
    }
  };

  const handleStaleSessionDetected = () => {
    // Signal that a stale session was detected and needs to be cleared
    setHasStaleSession(true);
  };

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-cyan-900 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 mb-4">
            <div className="relative w-16 h-16">
              <div className="absolute inset-0 border-4 border-cyan-400/20 rounded-full"></div>
              <div className="absolute inset-0 border-4 border-transparent border-t-cyan-400 rounded-full animate-spin"></div>
            </div>
          </div>
          <p className="text-gray-300 text-lg">Initializing authentication...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <LoginPage
        onLogin={handleLogin}
        hasStaleSession={hasStaleSession}
        onStaleSessionDetected={handleStaleSessionDetected}
      />
    );
  }

  return <Dashboard onLogout={handleLogout} />;
}

export default App;