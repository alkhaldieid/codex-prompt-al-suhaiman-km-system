import { DocumentShell } from "@/components/DocumentShell";

export default async function DocumentPage({params}: {params: Promise<{doc_id: string}>}) {
  const {doc_id} = await params;
  return <DocumentShell docId={doc_id} />;
}
