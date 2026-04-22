import { Metadata } from "next";
import { supabaseAdmin } from "@/lib/supabase-admin";
import CompaniesPageClient from "./CompaniesPageClient";

export const revalidate = 3600;

const BASE_URL = "https://fonrapor.com";

async function getCompanies() {
  const { data, error } = await supabaseAdmin
    .from("companies")
    .select("id, name, slug, display_name, logo, fund_count, total_aum")
    .order("fund_count", { ascending: false });

  if (error) throw error;
  return data || [];
}

export async function generateMetadata(): Promise<Metadata> {
  const companies = await getCompanies();
  const totalFunds = companies.reduce((s: number, c: any) => s + (c.fund_count || 0), 0);

  return {
    title: `Yatırım Şirketleri (${companies.length} şirket, ${totalFunds.toLocaleString("tr-TR")} fon) | FonRapor`,
    description: `Türkiye'deki yatırım fonu yönetim şirketleri. Toplam ${companies.length} şirket, ${totalFunds.toLocaleString("tr-TR")} fon. Fon sayısı ve toplam AUM'a göre sıralı.`,
    openGraph: {
      type: "website",
      locale: "tr_TR",
      url: `${BASE_URL}/companies`,
      siteName: "FonRapor",
      title: `Yatırım Şirketleri | FonRapor`,
      description: `${companies.length} yönetim şirketi, ${totalFunds.toLocaleString("tr-TR")} fon.`,
    },
    alternates: { canonical: `${BASE_URL}/companies` },
  };
}

export default async function CompaniesPage() {
  const companies = await getCompanies();

  return <CompaniesPageClient companies={companies} />;
}
