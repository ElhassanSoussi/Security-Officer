/** @type {import('next').NextConfig} */
const nextConfig = {
    experimental: {
        serverActions: {
            bodySizeLimit: "15mb",
        },
    },
};

export default nextConfig;

// Route Handler body size is controlled via the export in each route file.
// See: frontend/app/api/v1/[...path]/route.ts → maxDuration, runtime exports.
