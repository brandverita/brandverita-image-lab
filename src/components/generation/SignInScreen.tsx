import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/integrations/supabase/client";

type Props = {
  /** Set when a session exists but the email is not on the approved list. */
  unauthorizedEmail?: string | null;
  onSignOut?: () => void;
};

export function SignInScreen({ unauthorizedEmail, onSignOut }: Props) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function sendLink(target: string) {
    setBusy(true);
    setError(null);
    const { error: otpError } = await supabase.auth.signInWithOtp({
      email: target,
      options: { emailRedirectTo: window.location.origin, shouldCreateUser: true },
    });
    setBusy(false);

    if (otpError) {
      const status = otpError.status ?? 0;
      setError(
        status === 429
          ? "Too many requests. Wait a minute before asking for another link."
          : status === 422
            ? "That email address looks invalid."
            : "Could not send the sign-in link. Please try again.",
      );
      return;
    }
    setSentTo(target);
  }

  if (unauthorizedEmail) {
    return (
      <div className="mx-auto w-full max-w-md rounded-lg border border-border bg-card p-6">
        <h2 className="text-left text-lg font-semibold tracking-tight text-foreground">
          Access not authorized
        </h2>
        <div
          role="alert"
          className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
        >
          <span className="font-medium">{unauthorizedEmail}</span> is not authorized for the
          generation test. Ask the BrandVerita team to add your address to the approved list.
        </div>
        <Button variant="outline" className="mt-5" onClick={onSignOut}>
          Use a different email
        </Button>
      </div>
    );
  }

  if (sentTo) {
    return (
      <div className="mx-auto w-full max-w-md rounded-lg border border-border bg-card p-6">
        <h2 className="text-left text-lg font-semibold tracking-tight text-foreground">
          Check your inbox
        </h2>
        <p className="mt-3 text-sm text-muted-foreground">
          We sent a one-time sign-in link to <span className="font-medium text-foreground">{sentTo}</span>.
          Open it on this device to continue. The link expires after a short while.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Button variant="outline" disabled={busy} onClick={() => void sendLink(sentTo)}>
            {busy ? "Sending…" : "Resend link"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setSentTo(null);
              setError(null);
            }}
          >
            Use a different email
          </Button>
        </div>
        {error ? (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-md rounded-lg border border-border bg-card p-6">
      <h2 className="text-left text-lg font-semibold tracking-tight text-foreground">
        Sign in to continue
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">
        This development environment is limited to authorized BrandVerita email addresses. Enter your
        email and we&apos;ll send a one-time sign-in link — no password needed.
      </p>
      <form
        className="mt-5 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          void sendLink(email.trim());
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="magic-email">Work email</Label>
          <Input
            id="magic-email"
            type="email"
            autoComplete="email"
            required
            placeholder="you@brandverita.io"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <Button type="submit" className="w-full" disabled={busy || email.trim().length === 0}>
          {busy ? "Sending link…" : "Send magic link"}
        </Button>
      </form>
    </div>
  );
}
