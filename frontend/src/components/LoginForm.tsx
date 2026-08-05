/**
 * Login form component for authentication
 */

import React, { useState, FormEvent } from 'react';
import { useAuth } from '../context/AuthContext';
import type { LoginCredentials } from '../types/auth';

export const LoginForm: React.FC = () => {
  const { login, error, isLoading } = useAuth();
  const [credentials, setCredentials] = useState<LoginCredentials>({
    username: '',
    password: '',
  });
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLocalError(null);

    // Basic validation
    if (!credentials.username || !credentials.password) {
      setLocalError('Username and password are required');
      return;
    }

    try {
      await login(credentials);
      // Clear form on success
      setCredentials({ username: '', password: '' });
    } catch (err) {
      // Error is handled by AuthContext
      console.error('Login error:', err);
    }
  };

  const handleChange = (field: keyof LoginCredentials) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setCredentials((prev) => ({
      ...prev,
      [field]: e.target.value,
    }));
    setLocalError(null);
  };

  const displayError = localError || error;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg shadow-xl p-8 w-full max-w-md">
        <h2 className="text-2xl font-bold text-white mb-6">
          Aviation Intelligence Platform
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {displayError && (
            <div className="bg-red-900 bg-opacity-50 border border-red-500 text-red-200 px-4 py-3 rounded">
              {displayError}
            </div>
          )}

          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-2">
              Username
            </label>
            <input
              type="text"
              id="username"
              value={credentials.username}
              onChange={handleChange('username')}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter your username"
              disabled={isLoading}
              autoComplete="username"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
              Password
            </label>
            <input
              type="password"
              id="password"
              value={credentials.password}
              onChange={handleChange('password')}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter your password"
              disabled={isLoading}
              autoComplete="current-password"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-medium py-2 px-4 rounded-md transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-800"
          >
            {isLoading ? 'Logging in...' : 'Log In'}
          </button>
        </form>

        <div className="mt-6 text-sm text-gray-400 text-center">
          <p>For demo purposes, contact admin for credentials.</p>
        </div>
      </div>
    </div>
  );
};
