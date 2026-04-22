"use client";

import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "fonrapor_favorites";

export interface Favorite {
  code: string;
  name: string;
  addedAt: number;
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [loaded, setLoaded] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        setFavorites(JSON.parse(raw));
      }
    } catch {
      // ignore
    }
    setLoaded(true);
  }, []);

  // Persist to localStorage on change
  useEffect(() => {
    if (!loaded) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
    } catch {
      // ignore
    }
  }, [favorites, loaded]);

  const addFavorite = useCallback((code: string, name: string) => {
    setFavorites((prev) => {
      if (prev.find((f) => f.code === code)) return prev;
      return [...prev, { code, name, addedAt: Date.now() }];
    });
  }, []);

  const removeFavorite = useCallback((code: string) => {
    setFavorites((prev) => prev.filter((f) => f.code !== code));
  }, []);

  const toggleFavorite = useCallback((code: string, name: string) => {
    setFavorites((prev) => {
      const exists = prev.find((f) => f.code === code);
      if (exists) {
        return prev.filter((f) => f.code !== code);
      }
      return [...prev, { code, name, addedAt: Date.now() }];
    });
  }, []);

  const isFavorite = useCallback(
    (code: string) => favorites.some((f) => f.code === code),
    [favorites]
  );

  return {
    favorites,
    loaded,
    addFavorite,
    removeFavorite,
    toggleFavorite,
    isFavorite,
  };
}
