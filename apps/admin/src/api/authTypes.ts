export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "Bearer";
  expires_in: number;
}

export interface CurrentUserRole {
  id: string;
  code: string;
  name: string;
  scope_type: string;
  is_builtin: boolean;
  status: string;
}

export interface CurrentUserDepartment {
  id: string;
  code?: string | null;
  name: string;
  status: string;
  is_primary: boolean;
  is_default?: boolean;
}

export interface CurrentUserData {
  id: string;
  username: string;
  name: string;
  status: string;
}

export interface CurrentUserResponse {
  request_id: string;
  data: CurrentUserData;
}

export interface AdminCurrentUserCapabilitiesData extends CurrentUserData {
  departments: CurrentUserDepartment[];
  roles: CurrentUserRole[];
  scopes: string[];
}

export interface AdminCurrentUserCapabilitiesResponse {
  request_id: string;
  data: AdminCurrentUserCapabilitiesData;
}

export interface PasswordChangeRequest {
  old_password: string;
  new_password: string;
}
