import { AuthForm } from "@/components/auth-form";
import { safeAuthRedirect } from "@/lib/auth-redirect";

export default async function RegisterPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const next = (await searchParams).next;
  const destination = Array.isArray(next) ? next[0] : next;

  return <AuthForm mode="register" redirectTo={safeAuthRedirect(destination)} />;
}
