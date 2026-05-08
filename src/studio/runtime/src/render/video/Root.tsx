import { Composition } from "remotion";
import { SocialPost, type SocialPostProps } from "./SocialPost";

const givecare: SocialPostProps = {
  bg: "#FDF9EC",
  fg: "#3D1600",
  accent: "#FF9F00",
  headlineFont: "Alegreya, Georgia, serif",
  bodyFont: "Inter, system-ui, sans-serif",
  headline: "Care is infrastructure.",
  body: "63 million Americans provide unpaid care — worth $470 billion annually.",
  label: "CARE ECONOMY",
  textAlign: "left",
  contentRatio: 0.6,
  entrance: "spring",
  timing: "smooth",
  textureType: "pencil-grid",
  textureOpacity: 0.04,
};

const scty: SocialPostProps = {
  bg: "#FAFAFA",
  fg: "#111111",
  accent: "#FF3300",
  headlineFont: "JetBrains Mono, monospace",
  bodyFont: "Inter, system-ui, sans-serif",
  headline: "94% report no AI impact.",
  body: "The gap is execution, not tooling. Process, data, and org design didn't change.",
  label: "TRANSFORMATION GAP",
  textAlign: "left",
  contentRatio: 0.5,
  entrance: "cut",
  timing: "staccato",
  textureType: "halftone",
  textureOpacity: 0.06,
};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="givecare-landscape" component={SocialPost} durationInFrames={150} fps={30} width={1920} height={1080} defaultProps={givecare} />
    <Composition id="givecare-vertical" component={SocialPost} durationInFrames={150} fps={30} width={1080} height={1920} defaultProps={givecare} />
    <Composition id="scty-landscape" component={SocialPost} durationInFrames={150} fps={30} width={1920} height={1080} defaultProps={scty} />
    <Composition id="scty-vertical" component={SocialPost} durationInFrames={150} fps={30} width={1080} height={1920} defaultProps={scty} />
  </>
);
