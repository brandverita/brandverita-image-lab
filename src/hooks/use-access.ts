import { useCallback, useEffect, useState } from "react";

import { supabase } from "@/integrations/supabase/client";

type AccessState = "unknown" | "checking" | "allowed" | "denied" | "error";

/**
 * Asks the database whether the signed-in user's email is on the approved list.
 * The allow-list itself is never readable from the client.
 */
export function useAccessCheck(userId: string | null) {
  const [state, setState] = useState<AccessState>("unknown");
  const [message, setMessage] = useState<string | null>(null);

  const check = useCallback(async () => {
    if (!userId) {
      setState("unknown");
      setMessage(null);
      return;
    }
    setState("checking");
    // `current_user_allowed` is created by migration; types are regenerated separately.
    const { data, error } = await (
      supabase.rpc as unknown as (
        fn: string,
      ) => Promise<{ data: boolean | null; error: { message: string } | null }>
    )("current_user_allowed");

    if (error) {
      setState("error");
      setMessage("Could not verify access. Please try again.");
      return;
    }
    setMessage(null);
    setState(data === true ? "allowed" : "denied");
  }, [userId]);

  useEffect(() => {
    void check();
  }, [check]);

  return { access: state, accessMessage: message, recheck: check };
}
