import env from "@kosko/env";
import assert from "assert";
import { create } from "@socialgouv/kosko-charts/components/app";

const { deployment, ingress, service } = create(env.component("api"));

export default [deployment, ingress, service];
