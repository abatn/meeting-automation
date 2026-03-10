import React, { useEffect, useRef, useCallback } from "react";
import { useDispatch, useSelector } from "react-redux";
import { RootState, AppDispatch } from "../../store";
import { performLogout } from "../../store/authActions";
import { useNavigate } from "react-router-dom";

const TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes

const AutoLogout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();
  const { authState } = useSelector((state: RootState) => state.auth);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const resetTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    if (authState === "authenticated") {
      timerRef.current = setTimeout(() => {
        dispatch(performLogout());
        navigate("/login");
      }, TIMEOUT_MS);
    }
  }, [authState, dispatch, navigate]);

  useEffect(() => {
    if (authState !== "authenticated") {
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    // Set initial timer
    resetTimer();

    // Events to monitor for activity
    const events = ["mousemove", "keydown", "wheel", "click", "touchstart"];

    events.forEach((event) => {
      window.addEventListener(event, resetTimer);
    });

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      events.forEach((event) => {
        window.removeEventListener(event, resetTimer);
      });
    };
  }, [authState, resetTimer]);

  return <>{children}</>;
};

export default AutoLogout;
