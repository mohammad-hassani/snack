import Invitation from "../../../components/Invitation";
export default async function Page({ params }) {
  const { token } = await params;
  return <Invitation token={token} />;
}
