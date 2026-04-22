// Site-wide configuration constants
// VERCEL_URL is set automatically by Vercel to the current deployment URL
const VERCEL_URL = process.env.VERCEL_URL;
const PROD_URL = "https://web-vert-delta-62.vercel.app";

// The canonical URL of the deployed site (no trailing slash)
// Priority: VERCEL_URL (current deploy) > hardcoded production > fallback
export const HOME_PAGE_URL = VERCEL_URL
  ? `https://${VERCEL_URL}`
  : (process.env.NEXT_PUBLIC_SITE_URL || PROD_URL);
