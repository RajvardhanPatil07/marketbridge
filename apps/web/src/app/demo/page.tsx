import type { Metadata } from "next";
import { ProofLab } from "@/components/proof-lab";
import { WarRoom } from "@/components/v1-experience";

export const metadata: Metadata = {
  title: "Proof Lab + War Room",
};

export default function DemoPage() {
  return (
    <>
      <ProofLab />
      <WarRoom />
    </>
  );
}
