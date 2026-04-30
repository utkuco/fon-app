import { createClient } from "@supabase/supabase-js";

const supabaseUrl = "https://oqkobptbvcazifpvjwfz.supabase.co";
const supabaseAnonKey = "sb_publishable__GPrsdfKRZCMZE8to916iQ_Izv9naG-";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
