import { DEFAULT_CREATION_REQUIREMENTS } from "./Workspace";
export const PIPI_AUTHOR_ID = "douyin:xupp141010";
export type CreationDraft = {
  caseId: string;
  productId: string;
  draftName: string;
  writingMode: string;
  experience: string;
  requirements: string;
  learningIds: string[] | null;
};
export type CreationState = CreationDraft & {
  phase: "case" | "product" | "details" | "preview";
  requestKey: string;
  taskId: string;
};
export function emptyCreation(request = ""): CreationState {
  return {
    caseId: "",
    productId: "",
    draftName: "",
    writingMode: "生活分享",
    experience: "",
    requirements: request,
    learningIds: null,
    phase: "case",
    requestKey: crypto.randomUUID(),
    taskId: "",
  };
}
export function creationPayload(d: CreationState) {
  return {
    case_id: d.caseId,
    product_id: d.productId,
    author_id: PIPI_AUTHOR_ID,
    mode: "prototype",
    writing_mode: d.writingMode,
    personal_experience: d.experience.trim(),
    draft_name: d.draftName.trim(),
    learning_ids: d.learningIds,
    request_key: d.requestKey,
    extra_requirements:
      DEFAULT_CREATION_REQUIREMENTS +
      (d.requirements.trim()
        ? "\n\n【本次文案要求】\n" +
          d.requirements.trim() +
          "\n本次要求中的时长、口吻、受众、侧重点及禁用词优先于默认创作偏好；遵循真实产品资料和短句逐行、段间无空行的排版。仅借鉴参考案例的结构与节奏。"
        : ""),
  };
}
