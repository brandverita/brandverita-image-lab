export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      allowed_emails: {
        Row: {
          created_at: string
          email: string
          id: string
          note: string | null
        }
        Insert: {
          created_at?: string
          email: string
          id?: string
          note?: string | null
        }
        Update: {
          created_at?: string
          email?: string
          id?: string
          note?: string | null
        }
        Relationships: []
      }
      generation_assets: {
        Row: {
          bucket: string
          content_type: string | null
          created_at: string
          deleted_at: string | null
          expires_at: string | null
          file_size: number | null
          finalized_at: string | null
          height: number | null
          id: string
          idempotency_key: string | null
          job_id: string | null
          kind: string
          owner_id: string
          provenance: Json
          sha256: string | null
          source_asset_id: string | null
          status: string
          storage_path: string
          width: number | null
          workflow_key: string | null
          workflow_version: string | null
          workspace_id: string | null
        }
        Insert: {
          bucket: string
          content_type?: string | null
          created_at?: string
          deleted_at?: string | null
          expires_at?: string | null
          file_size?: number | null
          finalized_at?: string | null
          height?: number | null
          id?: string
          idempotency_key?: string | null
          job_id?: string | null
          kind?: string
          owner_id: string
          provenance?: Json
          sha256?: string | null
          source_asset_id?: string | null
          status?: string
          storage_path: string
          width?: number | null
          workflow_key?: string | null
          workflow_version?: string | null
          workspace_id?: string | null
        }
        Update: {
          bucket?: string
          content_type?: string | null
          created_at?: string
          deleted_at?: string | null
          expires_at?: string | null
          file_size?: number | null
          finalized_at?: string | null
          height?: number | null
          id?: string
          idempotency_key?: string | null
          job_id?: string | null
          kind?: string
          owner_id?: string
          provenance?: Json
          sha256?: string | null
          source_asset_id?: string | null
          status?: string
          storage_path?: string
          width?: number | null
          workflow_key?: string | null
          workflow_version?: string | null
          workspace_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "generation_assets_job_id_fkey"
            columns: ["job_id"]
            isOneToOne: false
            referencedRelation: "generation_jobs"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "generation_assets_source_asset_id_fkey"
            columns: ["source_asset_id"]
            isOneToOne: false
            referencedRelation: "generation_assets"
            referencedColumns: ["id"]
          },
        ]
      }
      generation_jobs: {
        Row: {
          completed_at: string | null
          created_at: string
          error_category: string | null
          error_code: string | null
          error_message: string | null
          expires_at: string | null
          height: number | null
          id: string
          idempotency_key: string | null
          input_asset_ids: string[] | null
          inputs: Json | null
          internal_error_ref: string | null
          modal_call_id: string | null
          negative_prompt: string | null
          output_asset_id: string | null
          output_asset_ids: string[] | null
          output_path: string | null
          output_preset: string | null
          progress: number
          prompt: string | null
          prompt_hash: string | null
          provider: string | null
          provider_job_reference: string | null
          provider_model: string | null
          queued_at: string | null
          request_params: Json
          result_url: string | null
          seed: number | null
          source_asset_id: string | null
          started_at: string | null
          status: string
          updated_at: string
          usage_ledger_id: string | null
          user_id: string
          width: number | null
          worker_version: string | null
          workflow_config_hash: string | null
          workflow_id: string
          workflow_version: string | null
          workspace_id: string | null
        }
        Insert: {
          completed_at?: string | null
          created_at?: string
          error_category?: string | null
          error_code?: string | null
          error_message?: string | null
          expires_at?: string | null
          height?: number | null
          id?: string
          idempotency_key?: string | null
          input_asset_ids?: string[] | null
          inputs?: Json | null
          internal_error_ref?: string | null
          modal_call_id?: string | null
          negative_prompt?: string | null
          output_asset_id?: string | null
          output_asset_ids?: string[] | null
          output_path?: string | null
          output_preset?: string | null
          progress?: number
          prompt?: string | null
          prompt_hash?: string | null
          provider?: string | null
          provider_job_reference?: string | null
          provider_model?: string | null
          queued_at?: string | null
          request_params?: Json
          result_url?: string | null
          seed?: number | null
          source_asset_id?: string | null
          started_at?: string | null
          status?: string
          updated_at?: string
          usage_ledger_id?: string | null
          user_id: string
          width?: number | null
          worker_version?: string | null
          workflow_config_hash?: string | null
          workflow_id: string
          workflow_version?: string | null
          workspace_id?: string | null
        }
        Update: {
          completed_at?: string | null
          created_at?: string
          error_category?: string | null
          error_code?: string | null
          error_message?: string | null
          expires_at?: string | null
          height?: number | null
          id?: string
          idempotency_key?: string | null
          input_asset_ids?: string[] | null
          inputs?: Json | null
          internal_error_ref?: string | null
          modal_call_id?: string | null
          negative_prompt?: string | null
          output_asset_id?: string | null
          output_asset_ids?: string[] | null
          output_path?: string | null
          output_preset?: string | null
          progress?: number
          prompt?: string | null
          prompt_hash?: string | null
          provider?: string | null
          provider_job_reference?: string | null
          provider_model?: string | null
          queued_at?: string | null
          request_params?: Json
          result_url?: string | null
          seed?: number | null
          source_asset_id?: string | null
          started_at?: string | null
          status?: string
          updated_at?: string
          usage_ledger_id?: string | null
          user_id?: string
          width?: number | null
          worker_version?: string | null
          workflow_config_hash?: string | null
          workflow_id?: string
          workflow_version?: string | null
          workspace_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "generation_jobs_output_asset_id_fkey"
            columns: ["output_asset_id"]
            isOneToOne: false
            referencedRelation: "generation_assets"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "generation_jobs_source_asset_id_fkey"
            columns: ["source_asset_id"]
            isOneToOne: false
            referencedRelation: "generation_assets"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "generation_jobs_usage_ledger_fk"
            columns: ["usage_ledger_id"]
            isOneToOne: false
            referencedRelation: "usage_ledger"
            referencedColumns: ["id"]
          },
        ]
      }
      generation_usage: {
        Row: {
          created_at: string
          gpu_seconds: number
          id: string
          jobs_count: number
          period: string
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          gpu_seconds?: number
          id?: string
          jobs_count?: number
          period: string
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          gpu_seconds?: number
          id?: string
          jobs_count?: number
          period?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      transformation_eval_runs: {
        Row: {
          actual_provider_cost: number | null
          blinded: boolean
          candidate_id: string | null
          cold_start: boolean | null
          commercial_status: string | null
          completed_at: string | null
          config_hash: string | null
          cost_currency: string | null
          created_at: string
          data_retention_finding: string | null
          dispatched_at: string | null
          error_code: string | null
          error_message: string | null
          estimated_cost: number | null
          first_byte_at: string | null
          gpu_seconds: number | null
          id: string
          job_id: string | null
          legal_reviewed_at: string | null
          legal_reviewed_by: string | null
          legal_status: string
          license_ref: string | null
          module: string
          notes: string | null
          operator_user_id: string
          output_asset_id: string | null
          output_bytes: number | null
          output_height: number | null
          output_preset: string | null
          output_sha256: string | null
          output_width: number | null
          provider: string
          provider_call_id: string | null
          provider_latency_ms: number | null
          provider_model: string | null
          queued_at: string | null
          request_params: Json
          reviewer_scores: Json
          rubric_mean: number | null
          source_asset_id: string | null
          source_region_verified: boolean | null
          status: string
          total_latency_ms: number | null
          training_on_input: boolean | null
          worker_version: string | null
          workflow_key: string
          workflow_version: string
        }
        Insert: {
          actual_provider_cost?: number | null
          blinded?: boolean
          candidate_id?: string | null
          cold_start?: boolean | null
          commercial_status?: string | null
          completed_at?: string | null
          config_hash?: string | null
          cost_currency?: string | null
          created_at?: string
          data_retention_finding?: string | null
          dispatched_at?: string | null
          error_code?: string | null
          error_message?: string | null
          estimated_cost?: number | null
          first_byte_at?: string | null
          gpu_seconds?: number | null
          id?: string
          job_id?: string | null
          legal_reviewed_at?: string | null
          legal_reviewed_by?: string | null
          legal_status?: string
          license_ref?: string | null
          module: string
          notes?: string | null
          operator_user_id: string
          output_asset_id?: string | null
          output_bytes?: number | null
          output_height?: number | null
          output_preset?: string | null
          output_sha256?: string | null
          output_width?: number | null
          provider: string
          provider_call_id?: string | null
          provider_latency_ms?: number | null
          provider_model?: string | null
          queued_at?: string | null
          request_params?: Json
          reviewer_scores?: Json
          rubric_mean?: number | null
          source_asset_id?: string | null
          source_region_verified?: boolean | null
          status?: string
          total_latency_ms?: number | null
          training_on_input?: boolean | null
          worker_version?: string | null
          workflow_key: string
          workflow_version: string
        }
        Update: {
          actual_provider_cost?: number | null
          blinded?: boolean
          candidate_id?: string | null
          cold_start?: boolean | null
          commercial_status?: string | null
          completed_at?: string | null
          config_hash?: string | null
          cost_currency?: string | null
          created_at?: string
          data_retention_finding?: string | null
          dispatched_at?: string | null
          error_code?: string | null
          error_message?: string | null
          estimated_cost?: number | null
          first_byte_at?: string | null
          gpu_seconds?: number | null
          id?: string
          job_id?: string | null
          legal_reviewed_at?: string | null
          legal_reviewed_by?: string | null
          legal_status?: string
          license_ref?: string | null
          module?: string
          notes?: string | null
          operator_user_id?: string
          output_asset_id?: string | null
          output_bytes?: number | null
          output_height?: number | null
          output_preset?: string | null
          output_sha256?: string | null
          output_width?: number | null
          provider?: string
          provider_call_id?: string | null
          provider_latency_ms?: number | null
          provider_model?: string | null
          queued_at?: string | null
          request_params?: Json
          reviewer_scores?: Json
          rubric_mean?: number | null
          source_asset_id?: string | null
          source_region_verified?: boolean | null
          status?: string
          total_latency_ms?: number | null
          training_on_input?: boolean | null
          worker_version?: string | null
          workflow_key?: string
          workflow_version?: string
        }
        Relationships: [
          {
            foreignKeyName: "transformation_eval_runs_job_id_fkey"
            columns: ["job_id"]
            isOneToOne: false
            referencedRelation: "generation_jobs"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "transformation_eval_runs_output_asset_id_fkey"
            columns: ["output_asset_id"]
            isOneToOne: false
            referencedRelation: "generation_assets"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "transformation_eval_runs_source_asset_id_fkey"
            columns: ["source_asset_id"]
            isOneToOne: false
            referencedRelation: "generation_assets"
            referencedColumns: ["id"]
          },
        ]
      }
      usage_ledger: {
        Row: {
          actual_provider_cost: number | null
          created_at: string
          estimated_credits: number | null
          estimated_provider_cost: number | null
          gpu_seconds: number | null
          id: string
          job_id: string | null
          provider: string
          settled_at: string | null
          status: string
          user_id: string
          workflow_key: string
          workflow_version: string
          workspace_id: string | null
        }
        Insert: {
          actual_provider_cost?: number | null
          created_at?: string
          estimated_credits?: number | null
          estimated_provider_cost?: number | null
          gpu_seconds?: number | null
          id?: string
          job_id?: string | null
          provider: string
          settled_at?: string | null
          status?: string
          user_id: string
          workflow_key: string
          workflow_version: string
          workspace_id?: string | null
        }
        Update: {
          actual_provider_cost?: number | null
          created_at?: string
          estimated_credits?: number | null
          estimated_provider_cost?: number | null
          gpu_seconds?: number | null
          id?: string
          job_id?: string | null
          provider?: string
          settled_at?: string | null
          status?: string
          user_id?: string
          workflow_key?: string
          workflow_version?: string
          workspace_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "usage_ledger_job_id_fkey"
            columns: ["job_id"]
            isOneToOne: false
            referencedRelation: "generation_jobs"
            referencedColumns: ["id"]
          },
        ]
      }
      workflow_definitions: {
        Row: {
          allowed_dimensions: Json
          allowed_envs: string[]
          allowed_output_presets: Json
          allowed_workspace_ids: string[] | null
          artifact_pins: Json
          candidate_id: string | null
          candidate_notes: string | null
          comfyui_ref: string | null
          commercial_status: string
          config_hash: string | null
          created_at: string
          data_handling_profile: string | null
          description: string | null
          display_name: string | null
          enabled_for_studio: boolean
          estimated_credits: number | null
          feature_flag: string | null
          id: string
          input_envelope: Json
          input_schema: Json
          key: string
          model_manifest_ref: string | null
          output_schema: Json
          production_enabled: boolean
          provider: string
          provider_model: string | null
          provider_terms_reference: string | null
          provider_terms_verified_at: string | null
          provider_workflow_reference: string | null
          registry_visibility: string
          requires_source_asset: boolean
          retired_at: string | null
          rollout_percentage: number
          status: string
          version: string
          worker_version: string | null
        }
        Insert: {
          allowed_dimensions?: Json
          allowed_envs?: string[]
          allowed_output_presets?: Json
          allowed_workspace_ids?: string[] | null
          artifact_pins?: Json
          candidate_id?: string | null
          candidate_notes?: string | null
          comfyui_ref?: string | null
          commercial_status?: string
          config_hash?: string | null
          created_at?: string
          data_handling_profile?: string | null
          description?: string | null
          display_name?: string | null
          enabled_for_studio?: boolean
          estimated_credits?: number | null
          feature_flag?: string | null
          id?: string
          input_envelope?: Json
          input_schema?: Json
          key: string
          model_manifest_ref?: string | null
          output_schema?: Json
          production_enabled?: boolean
          provider: string
          provider_model?: string | null
          provider_terms_reference?: string | null
          provider_terms_verified_at?: string | null
          provider_workflow_reference?: string | null
          registry_visibility?: string
          requires_source_asset?: boolean
          retired_at?: string | null
          rollout_percentage?: number
          status?: string
          version: string
          worker_version?: string | null
        }
        Update: {
          allowed_dimensions?: Json
          allowed_envs?: string[]
          allowed_output_presets?: Json
          allowed_workspace_ids?: string[] | null
          artifact_pins?: Json
          candidate_id?: string | null
          candidate_notes?: string | null
          comfyui_ref?: string | null
          commercial_status?: string
          config_hash?: string | null
          created_at?: string
          data_handling_profile?: string | null
          description?: string | null
          display_name?: string | null
          enabled_for_studio?: boolean
          estimated_credits?: number | null
          feature_flag?: string | null
          id?: string
          input_envelope?: Json
          input_schema?: Json
          key?: string
          model_manifest_ref?: string | null
          output_schema?: Json
          production_enabled?: boolean
          provider?: string
          provider_model?: string | null
          provider_terms_reference?: string | null
          provider_terms_verified_at?: string | null
          provider_workflow_reference?: string | null
          registry_visibility?: string
          requires_source_asset?: boolean
          retired_at?: string | null
          rollout_percentage?: number
          status?: string
          version?: string
          worker_version?: string | null
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      current_user_allowed: { Args: never; Returns: boolean }
      is_email_allowed: { Args: { _user_id: string }; Returns: boolean }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
