CREATE SCHEMA idle_rpg_bot
  AUTHORIZATION idle_rpg_bot;

CREATE table idle_rpg_bot.user_locales
(
  telegram_id integer,
  locale      text
);
alter table  idle_rpg_bot.user_locales owner to idle_rpg_bot;
create unique index ind_user_locales_telegram_id_u on idle_rpg_bot.user_locales(telegram_id);