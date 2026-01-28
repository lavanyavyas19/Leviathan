import React, { useState } from 'react';
import { signIn } from 'aws-amplify/auth';

const LoginPage = ({ onLogin }) => {
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      await signIn({
        username: credentials.username,
        password: credentials.password
      });

      setTimeout(() => {
        setIsLoading(false);
        onLogin();
      }, 2500);
    } catch (err) {
      setError(err.message || 'Authentication failed');
      setIsLoading(false);
      console.error('Auth error:', err);
    }
  };

  const handleChange = (e) => {
    setCredentials({
      ...credentials,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-cyan-900 flex items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 opacity-20">
        <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-r from-transparent via-cyan-500 to-transparent animate-pulse"></div>
        <div className="absolute top-1/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-teal-400 to-transparent animate-pulse delay-1000"></div>
        <div className="absolute top-2/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent animate-pulse delay-2000"></div>
        <div className="absolute top-3/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-teal-500 to-transparent animate-pulse delay-3000"></div>
      </div>

      <div className="bg-slate-800/80 backdrop-blur-lg p-8 rounded-xl border border-cyan-500/30 shadow-2xl shadow-cyan-500/20 w-full max-w-md relative">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-cyan-400 to-teal-600 rounded-full mb-4 shadow-lg shadow-cyan-500/30">
            <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2L2 7v10c0 5.55 3.84 9.74 9 9.74s9-4.19 9-9.74V7L12 2z"/>
            </svg>
          </div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-teal-400 bg-clip-text text-transparent">
            LEVIATHAN
          </h1>
          <p className="text-gray-400 text-sm mt-2">Maritime Surveillance System</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Username</label>
            <input
              type="text"
              name="username"
              value={credentials.username}
              onChange={handleChange}
              className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-lg focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 text-white placeholder-gray-400 transition-all"
              placeholder="Enter your username"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Password</label>
            <input
              type="password"
              name="password"
              value={credentials.password}
              onChange={handleChange}
              className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-lg focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 text-white placeholder-gray-400 transition-all"
              placeholder="Enter your password"
              required
            />
          </div>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 px-4 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white font-semibold rounded-lg shadow-lg shadow-cyan-500/30 transition-all duration-300 transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed relative overflow-hidden"
          >
            {isLoading ? (
              <div className="flex items-center justify-center">
                <div className="relative w-8 h-8 mr-3">
                  <div className="absolute inset-0 border-2 border-cyan-400/20 rounded-full"></div>
                  <div className="absolute inset-0 border-2 border-transparent border-t-cyan-400 rounded-full animate-spin"></div>
                  <div className="absolute top-1/2 left-1/2 w-1 h-3 bg-cyan-400 transform -translate-x-1/2 -translate-y-1/2 origin-bottom animate-pulse"></div>
                </div>
                <div className="flex flex-col">
                  <span className="text-sm">Establishing Connection...</span>
                  <span className="text-xs opacity-80">Scanning Maritime Networks</span>
                </div>
              </div>
            ) : (
              <span className="flex items-center justify-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Navigate to Command Center
              </span>
            )}
          </button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-xs text-gray-500">Authorized personnel only</p>
          <p className="text-xs text-gray-600 mt-1">v2.1.4 • Secure Maritime Operations</p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;