import Auth from "../../../components/Auth";
export default async function Page({ params }) {
  const { path } = await params;
  return <Auth path={path} />;
}
