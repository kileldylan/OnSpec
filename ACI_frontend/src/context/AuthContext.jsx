import { createContext, useContext, useEffect, useState } from 'react';
import { aciApi } from '../api/aci';

const AuthContext = createContext(null);

const withCsrf = async () => {
  const response = await aciApi.getCsrfToken();
  return response.data.csrfToken;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    aciApi.getCurrentUser()
      .then((response) => setUser(response.data.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (credentials) => {
    const csrfToken = await withCsrf();
    const response = await aciApi.login(credentials, csrfToken);
    setUser(response.data.user);
  };

  const register = async (details) => {
    const csrfToken = await withCsrf();
    const response = await aciApi.register(details, csrfToken);
    setUser(response.data.user);
  };

  const logout = async () => {
    const csrfToken = await withCsrf();
    await aciApi.logout(csrfToken);
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