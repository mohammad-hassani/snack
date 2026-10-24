const backend = process.env.DJANGO_URL || "http://127.0.0.1:8000";
export default {
  trailingSlash: true,
  async rewrites() {
    return [
      { source: "/static/:path*", destination: `${backend}/static/:path*` },
      ...["api", "files", "ws", "admin", "health"].map((path) => ({
        source: `/${path}/:path*/`,
        destination: `${backend}/${path}/:path*/`,
      })),
    ];
  },
};
