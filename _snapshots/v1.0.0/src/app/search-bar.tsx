"use client";

import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";

export function SearchBar({ defaultValue }: { defaultValue: string }) {
  const router = useRouter();

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);
        const q = formData.get("q") as string;
        router.push(q ? `/?q=${encodeURIComponent(q)}` : "/");
      }}
      className="max-w-md mx-auto"
    >
      <Input
        name="q"
        placeholder="Fon kodu, adı veya yönetici ara..."
        defaultValue={defaultValue}
        className="h-11"
      />
    </form>
  );
}
