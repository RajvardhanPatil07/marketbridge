import type { Metadata } from "next";
import { JudgeControls } from "@/components/judge-controls";
import { ProofLab } from "@/components/proof-lab";
import { WarRoom } from "@/components/v1-experience";

export const metadata: Metadata = {
  title: "Judge Mode · Proof Lab + War Room",
};

export default function DemoPage() {
  return (
    <>
      <JudgeControls />
      <ProofLab />
      <WarRoom />
    </>
  );
}