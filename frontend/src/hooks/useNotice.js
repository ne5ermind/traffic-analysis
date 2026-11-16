import {useCallback, useEffect, useRef, useState} from 'react';

export function useNotice() {
  const [notice, setNotice] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  const flash = useCallback((message, ok = false) => {
    clearTimeout(timerRef.current);
    setNotice({message, ok});
    timerRef.current = setTimeout(() => setNotice(null), 7000);
  }, []);

  return {notice, flash};
}
