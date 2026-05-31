import { useEffect, PropsWithChildren } from 'react';
import { useUserStore } from './stores/user';
import './app.scss';

export default function App({ children }: PropsWithChildren) {
  const fetchUser = useUserStore((s) => s.fetchUser);

  useEffect(() => {
    fetchUser();
  }, []);

  return children;
}
