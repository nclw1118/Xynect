import WorkspaceShell from "@/components/workspace/WorkspaceShell";

export const metadata = { title: "Workspace — Xynect" };

export default async function WorkspacePage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <WorkspaceShell sessionId={sessionId} />;
}
