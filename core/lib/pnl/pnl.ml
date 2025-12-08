(** P&L (Profit and Loss) Calculator

    Calculates realized and unrealized P&L for positions.
    Handles fee deduction and provides detailed trade analytics.
*)

open Types

(** Fee structure *)
type fee_structure = {
  maker_fee: float;  (** Maker fee rate (e.g., 0.001 = 0.1%) *)
  taker_fee: float;  (** Taker fee rate *)
} [@@deriving yojson, show]

let binance_vip0_fees = {
  maker_fee = 0.001;  (* 0.1% *)
  taker_fee = 0.001;  (* 0.1% *)
}

(** Calculate fee for a trade *)
let calculate_fee ~price ~quantity ~is_maker fees =
  let rate = if is_maker then fees.maker_fee else fees.taker_fee in
  Decimal.(price * quantity * of_float rate)

(** Trade P&L breakdown *)
type trade_pnl = {
  gross_pnl: Decimal.t;      (** P&L before fees *)
  fees_paid: Decimal.t;       (** Total fees *)
  net_pnl: Decimal.t;         (** P&L after fees *)
  entry_price: Decimal.t;
  exit_price: Decimal.t;
  quantity: Decimal.t;
  holding_time_secs: float;
} [@@deriving yojson, show]

(** Calculate P&L for a closing trade *)
let calculate_trade_pnl ~entry_price ~exit_price ~quantity ~side ~entry_time ~exit_time fees =
  let gross_pnl = match side with
    | Buy ->  (* Long position closed *)
      Decimal.((exit_price - entry_price) * quantity)
    | Sell -> (* Short position closed *)
      Decimal.((entry_price - exit_price) * quantity)
  in
  let entry_fee = calculate_fee ~price:entry_price ~quantity ~is_maker:false fees in
  let exit_fee = calculate_fee ~price:exit_price ~quantity ~is_maker:false fees in
  let total_fees = Decimal.(entry_fee + exit_fee) in
  {
    gross_pnl;
    fees_paid = total_fees;
    net_pnl = Decimal.(gross_pnl - total_fees);
    entry_price;
    exit_price;
    quantity;
    holding_time_secs = exit_time -. entry_time;
  }

(** Position state for tracking P&L *)
type position_state = {
  symbol: Symbol.t;
  side: side;
  quantity: Decimal.t;
  avg_entry_price: Decimal.t;
  realized_pnl: Decimal.t;
  trades: trade list;
  entry_time: float;
} [@@deriving yojson, show]

let empty_position symbol = {
  symbol;
  side = Buy;  (* Default, will be set on first trade *)
  quantity = Decimal.zero;
  avg_entry_price = Decimal.zero;
  realized_pnl = Decimal.zero;
  trades = [];
  entry_time = Unix.gettimeofday ();
}

(** Update position with a new trade *)
let update_position pos (trade: trade) fees =
  let current_qty = pos.quantity in
  let trade_qty = trade.quantity in

  (* Check if this trade increases or decreases position *)
  let is_opening = match pos.side, trade.side with
    | Buy, Buy -> true
    | Sell, Sell -> true
    | Buy, Sell -> false
    | Sell, Buy -> false
  in

  if Decimal.is_zero current_qty then
    (* Opening a new position *)
    {
      pos with
      side = trade.side;
      quantity = trade_qty;
      avg_entry_price = trade.price;
      trades = trade :: pos.trades;
      entry_time = trade.timestamp;
    }
  else if is_opening then
    (* Adding to existing position - calculate new average price *)
    let total_value = Decimal.(pos.avg_entry_price * current_qty + trade.price * trade_qty) in
    let new_qty = Decimal.(current_qty + trade_qty) in
    let new_avg = Decimal.(total_value / new_qty) in
    {
      pos with
      quantity = new_qty;
      avg_entry_price = new_avg;
      trades = trade :: pos.trades;
    }
  else
    (* Closing/reducing position *)
    let close_qty = if Decimal.(trade_qty > current_qty) then current_qty else trade_qty in
    let pnl = calculate_trade_pnl
      ~entry_price:pos.avg_entry_price
      ~exit_price:trade.price
      ~quantity:close_qty
      ~side:pos.side
      ~entry_time:pos.entry_time
      ~exit_time:trade.timestamp
      fees
    in
    let remaining_qty = Decimal.(current_qty - close_qty) in
    {
      pos with
      quantity = remaining_qty;
      realized_pnl = Decimal.(pos.realized_pnl + pnl.net_pnl);
      trades = trade :: pos.trades;
    }

(** Calculate unrealized P&L for a position *)
let unrealized_pnl pos current_price =
  if Decimal.is_zero pos.quantity then Decimal.zero
  else
    match pos.side with
    | Buy -> Decimal.((current_price - pos.avg_entry_price) * pos.quantity)
    | Sell -> Decimal.((pos.avg_entry_price - current_price) * pos.quantity)

(** Calculate total P&L (realized + unrealized) *)
let total_pnl pos current_price =
  Decimal.(pos.realized_pnl + unrealized_pnl pos current_price)

(** Performance metrics *)
type performance_metrics = {
  total_trades: int;
  winning_trades: int;
  losing_trades: int;
  win_rate: float;
  total_pnl: Decimal.t;
  total_fees: Decimal.t;
  gross_profit: Decimal.t;
  gross_loss: Decimal.t;
  profit_factor: float;
  avg_win: Decimal.t;
  avg_loss: Decimal.t;
  largest_win: Decimal.t;
  largest_loss: Decimal.t;
  avg_holding_time_secs: float;
} [@@deriving yojson, show]

(** Calculate performance metrics from trade history *)
let calculate_metrics (trades: trade_pnl list) : performance_metrics =
  let winning = List.filter (fun t -> Decimal.is_positive t.net_pnl) trades in
  let losing = List.filter (fun t -> Decimal.is_negative t.net_pnl) trades in

  let sum_pnl lst = List.fold_left (fun acc t -> Decimal.(acc + t.net_pnl)) Decimal.zero lst in
  let sum_fees lst = List.fold_left (fun acc t -> Decimal.(acc + t.fees_paid)) Decimal.zero lst in
  let sum_time lst = List.fold_left (fun acc t -> acc +. t.holding_time_secs) 0.0 lst in

  let total = List.length trades in
  let winners = List.length winning in
  let losers = List.length losing in

  let gross_profit = sum_pnl winning in
  let gross_loss = Decimal.abs (sum_pnl losing) in

  let max_pnl lst = List.fold_left (fun acc t ->
    if Decimal.(t.net_pnl > acc) then t.net_pnl else acc
  ) Decimal.zero lst in

  let min_pnl lst = List.fold_left (fun acc t ->
    if Decimal.(t.net_pnl < acc) then t.net_pnl else acc
  ) Decimal.zero lst in

  {
    total_trades = total;
    winning_trades = winners;
    losing_trades = losers;
    win_rate = if total > 0 then Float.of_int winners /. Float.of_int total else 0.0;
    total_pnl = sum_pnl trades;
    total_fees = sum_fees trades;
    gross_profit;
    gross_loss;
    profit_factor = if Decimal.is_zero gross_loss then 0.0
                    else Decimal.to_float Decimal.(gross_profit / gross_loss);
    avg_win = if winners > 0 then Decimal.(gross_profit / of_float (Float.of_int winners)) else Decimal.zero;
    avg_loss = if losers > 0 then Decimal.(gross_loss / of_float (Float.of_int losers)) else Decimal.zero;
    largest_win = max_pnl trades;
    largest_loss = Decimal.abs (min_pnl trades);
    avg_holding_time_secs = if total > 0 then sum_time trades /. Float.of_int total else 0.0;
  }
