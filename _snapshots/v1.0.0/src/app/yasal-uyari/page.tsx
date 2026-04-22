import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Yasal Uyarı",
  description:
    "FonRapor.com yasal uyarı ve feragatname — sunulan bilgiler yatırım danışmanlığı kapsamında değildir.",
};

export default function YasalUyariPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold text-neutral-900 mb-6">Yasal Uyarı ve Feragatname</h1>

      <div className="space-y-4 text-sm text-neutral-700 leading-relaxed">
        <p>
          Bu sitede yer alan bilgi, değerlendirme, yorum ve istatistikler{' '}
          <strong>genel bilgilendirme amaçlıdır</strong>. Sunulan bilgiler, Sermaye
          Piyasasası Kanunu kapsamında yatırım danışmanlığı hizmeti teşkil etmez ve belirli
          bir yatırımcının risk-getiri profiline göre kişiselleştirilmiş değildir.
        </p>

        <p>
          FonRapor.com, yalnızca kamuya açık verileri (TEFAS, KAP ve fon izahnameleri)
          derleyerek sunmaktadır. Site üzerinde sunulan fon bilgileri, performans verileri,
          sıralamalar ve karşılaştırmalar <strong>sadece bilgi amaçlıdır</strong>.
        </p>

        <div className="border-l-4 border-amber-400 pl-4 py-1 bg-amber-50 rounded">
          <p className="text-amber-900 font-medium text-xs uppercase tracking-wide mb-1">
            Önemli Uyarı
          </p>
          <p className="text-amber-800 text-sm">
            Geçmiş performans, gelecekteki getirilerin garantisi değildir. Yatırım fonları
            sermaye piyasası araçlarıdır ve yatırım riski içerir. Fon birim değerleri piyasa
            koşullarına göre değişebilir.
          </p>
        </div>

        <h2 className="text-base font-semibold text-neutral-900 pt-2">
          Site Hakkında Sorumluluk
        </h2>
        <p>
          Site içeriğinde yer alan hiçbir bilgi, yorum veya değerlendirme yatırım tavsiyesi
          olarak yorumlanmamalıdır. FonRapor.com&apos;da yer alan her türlü bilgi ve
          karşılaştırma, yatırımcıların kendi araştırmelerini yapmalarini desteklemek amacıyla
          sunulmaktadır.
        </p>

        <p>
          Bu sitedeki bilgiler kullanılarak yapılan yatırım kararlarından kaynaklanan herhangi
          bir zarardan FonRapor.com sorumlu değildir. Detaylı fon bilgileri, risk faktörleri
          ve yatırım kararları için fon izahnamesi ve Kamuyu Aydınlatma Platformu (KAP){' '}
          <strong>mutlaka incelenmelidir</strong>.
        </p>

        <h2 className="text-base font-semibold text-neutral-900 pt-2">
          Veri Kaynakları ve Doğruluk
        </h2>
        <p>
          Sitede kullanılan tüm veriler TEFAS (Türkiye Elektronik Fon Alım Satım Sistemi) ve
          KAP (Kamuyu Aydınlatma Platformu) resmi veri kaynaklarından alınmaktadır. Verilerin
          doğruluğu ve güncelliği konusunda makul özen gösterilmekle birlikte, FonRapor.com
          sunulan verilerin %100 doğru olacağını garanti etmez.
        </p>

        <h2 className="text-base font-semibold text-neutral-900 pt-2">Telif Hakkı</h2>
        <p>
          Sitenin tüm içeriği (logolar, fon isimleri, performans verileri dahil) kamuya açık
          bilgilerden derlenmiştir. Fonda bulunan şirket logoları ve fon isimleri ilgili
          yönetim şirketlerinin ticari markalarıdır ve telif hakkı sahiplerine aittir.
        </p>

        <div className="border-t border-neutral-200 pt-4 mt-6 text-xs text-neutral-500">
          <p>Son güncelleme: {new Date().toLocaleDateString("tr-TR", { day: "2-digit", month: "long", year: "numeric" })}</p>
        </div>
      </div>
    </main>
  );
}
