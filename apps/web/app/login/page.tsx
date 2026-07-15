import { AuthForm } from "@/components/auth-form";
import { safeAuthRedirect } from "@/lib/auth-api";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const next = (await searchParams).next;
  const destination = Array.isArray(next) ? next[0] : next;

  return <AuthForm mode="login" redirectTo={safeAuthRedirect(destination)} />;
}
