import { test, expect } from "@playwright/test";

test("project workspace and accessible creation form", async ({ page }) => {
  const failures: string[] = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Транспортные потоки", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Новый проект", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Название проекта", exact: true })
    .fill("Проверка интерфейса");
  await expect(
    page.getByRole("button", { name: "Создать проект", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Выбрать видео" }),
  ).toBeAttached();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Отмена", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Транспортные потоки", exact: true }),
  ).toBeVisible();
  expect(failures).toEqual([]);
});
