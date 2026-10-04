export const url = (path: string) => `/api${path}`;
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(url(path), {
    ...options,
    headers:
      options.body instanceof FormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    let message = "Не удалось выполнить запрос";
    try {
      const body = await response.json();
      message =
        typeof body.detail === "string"
          ? body.detail
          : body.detail?.map((e: { msg: string }) => e.msg).join("; ") ||
            message;
    } catch {
      /* HTTP body may be empty */
    }
    throw new Error(message);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export function upload(
  path: string,
  file: File,
  onProgress: (p: number) => void,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url(path));
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable)
        onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () =>
      reject(new Error("Соединение прервано. Повторите загрузку."));
    xhr.onload = () => {
      let body;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        reject(new Error("Не удалось загрузить файл"));
        return;
      }
      if (xhr.status < 300) resolve(body);
      else reject(new Error(body.detail || "Ошибка загрузки"));
    };
    const data = new FormData();
    data.append("file", file);
    xhr.send(data);
  });
}
