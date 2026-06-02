export interface PaginationData {
  page: number;
  page_size: number;
  total: number;
}

export interface AcceptedResponse {
  request_id: string;
  data: {
    accepted: boolean;
    job_id: string | null;
  };
}
