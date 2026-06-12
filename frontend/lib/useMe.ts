"use client";
import { useEffect, useState } from "react";
import { api, ApiError, Me } from "./api";

export function useMe() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<number | null>(null);

  useEffect(() => {
    api
      .get<Me>("/auth/me")
      .then(setMe)
      .catch((e: ApiError) => setError(e.status ?? 500))
      .finally(() => setLoading(false));
  }, []);

  return { me, loading, error };
}
