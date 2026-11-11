import { createContext, useContext, useEffect, useState } from 'react';
import { requoraApi } from '../api/requora';

const AuthContext = createContext(null);

const withCsrf = async () => {
  const response = await requoraApi.getCsrfToken();
  return response.data.csrfToken;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    requoraApi.getCurrentUser()
      .then((response) => setUser(response.data.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (credentials) => {
    const csrfToken = await withCsrf();
    const response = await requoraApi.login(credentials, csrfToken);
    setUser(response.data.user);
  };

  const register = async (details) => {
    const csrfToken = await withCsrf();
    const response = await requoraApi.register(details, csrfToken);
    setUser(response.data.user);
  };

  const logout = async () => {
    const csrfToken = await withCsrf();
    await requoraApi.logout(csrfToken);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};