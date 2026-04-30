import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "İletişim",
  description: "FonRapor.com ile iletişime geçin.",
};

export default function IletisimPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-2xl font-bold text-neutral-900 mb-6">İletişim</h1>

      <div className="space-y-6 text-sm text-neutral-700 leading-relaxed">
        <p>
          FonRapor.com ile iletişime geçmek için aşağıdaki kanalları kullanabilirsiniz.
          En kısa sürede size dönüş yapmaya çalışacağız.
        </p>

        <div className="border border-neutral-200 rounded-lg p-5 space-y-3">
          <div className="flex items-start gap-3">
            <span className="text-neutral-400 mt-0.5">✉️</span>
            <div>
              <p className="font-semibold text-neutral-900 text-xs uppercase tracking-wide">
                E-posta
              </p>
              <a
                href="mailto:bilgi@fonrapor.com"
                className="text-blue-600 hover:underline"
              >
                bilgi@fonrapor.com
              </a>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <span className="text-neutral-400 mt-0.5">🌐</span>
            <div>
              <p className="font-semibold text-neutral-900 text-xs uppercase tracking-wide">
                Web Sitesi
              </p>
              <a
                href="https://fonrapor.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                fonrapor.com
              </a>
            </div>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-100 rounded-lg p-4">
          <p className="text-blue-900 text-xs">
            <strong>Not:</strong> FonRapor.com yalnızca bir bilgi platformudur ve
            yatırım danışmanlığı hizmeti sunmamaktadır. Fon seçimi ve yatırım kararları
            için bir finansal danışmana başvurmanızı öneririz.
          </p>
        </div>

        <p className="text-xs text-neutral-500">
          Taleplerinize 24-48 iş günü içinde dönüş yapmaya çalışıyoruz.
        </p>
      </div>
    </main>
  );
}
