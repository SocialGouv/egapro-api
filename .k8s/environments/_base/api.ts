import { AppComponentEnvironment } from "@socialgouv/kosko-charts/components/app/params";
import { ok } from "assert";

ok(process.env.CI_REGISTRY_IMAGE);
ok(process.env.CI_COMMIT_SHA);

const env: AppComponentEnvironment = {
  containerPort: 3000,

  image: {
    name: process.env.CI_REGISTRY_IMAGE,
    tag: process.env.CI_COMMIT_TAG ? process.env.CI_COMMIT_TAG.slice(1) : process.env.CI_COMMIT_SHA,
  },

  ingress: {
    secretName: process.env.PRODUCTION ? "www-crt" : "wildcard-crt",
  },

  labels: {
    component: "cdtn-api",
  },
  name: "api",
  
  requests: {
    cpu: "100m",
    memory: "128Mi",
  },
  
  limits: {
    cpu: "1000m",
    memory: "256Mi",
  },

  servicePort: 80,
};

export default env;
