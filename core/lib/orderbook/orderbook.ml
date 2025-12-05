(** Order Book Management

    Type-safe order book representation with computed metrics.
    The order book is immutable - updates create new instances.
*)

open Types

module PriceMap = Map.Make(struct
  type t = Decimal.t
  let compare = Decimal.compare
end)

(** An immutable order book *)
type t = {
  symbol: Symbol.t;
  bids: Decimal.t PriceMap.t;  (** Price -> Quantity, sorted descending *)
  asks: Decimal.t PriceMap.t;  (** Price -> Quantity, sorted ascending *)
  last_update_id: int64;
  timestamp: int64;
}

let empty symbol = {
  symbol;
  bids = PriceMap.empty;
  asks = PriceMap.empty;
  last_update_id = 0L;
  timestamp = 0L;
}

(** Create from orderbook_state *)
let of_state (state: orderbook_state) : t =
  let bids = List.fold_left (fun acc level ->
    PriceMap.add level.price level.quantity acc
  ) PriceMap.empty state.bids in
  let asks = List.fold_left (fun acc level ->
    PriceMap.add level.price level.quantity acc
  ) PriceMap.empty state.asks in
  {
    symbol = state.symbol;
    bids;
    asks;
    last_update_id = state.last_update_id;
    timestamp = state.timestamp;
  }

(** Get best bid price and quantity *)
let best_bid t =
  PriceMap.max_binding_opt t.bids
  |> Option.map (fun (price, qty) -> { price; quantity = qty })

(** Get best ask price and quantity *)
let best_ask t =
  PriceMap.min_binding_opt t.asks
  |> Option.map (fun (price, qty) -> { price; quantity = qty })

(** Get mid price *)
let mid_price t =
  match best_bid t, best_ask t with
  | Some bid, Some ask ->
    let open Decimal in
    Some ((bid.price + ask.price) / of_float 2.0)
  | _ -> None

(** Get spread in basis points *)
let spread_bps t =
  match best_bid t, best_ask t, mid_price t with
  | Some bid, Some ask, Some mid when not (Decimal.is_zero mid) ->
    let open Decimal in
    Some (((ask.price - bid.price) / mid) * of_float 10000.0)
  | _ -> None

(** Calculate simple imbalance at top N levels *)
let imbalance ?(levels=5) t =
  let take_n n map =
    PriceMap.to_seq map
    |> Seq.take n
    |> List.of_seq
  in
  let bid_levels = take_n levels t.bids in
  let ask_levels = take_n levels t.asks in
  let bid_vol = List.fold_left (fun acc (_, qty) -> Decimal.(acc + qty)) Decimal.zero bid_levels in
  let ask_vol = List.fold_left (fun acc (_, qty) -> Decimal.(acc + qty)) Decimal.zero ask_levels in
  let total = Decimal.(bid_vol + ask_vol) in
  if Decimal.is_zero total then None
  else Some Decimal.((bid_vol - ask_vol) / total)

(** Calculate weighted imbalance with exponential decay *)
let weighted_imbalance ?(levels=10) ?(decay=0.9) t =
  let weighted_sum map =
    PriceMap.to_seq map
    |> Seq.take levels
    |> Seq.mapi (fun i (_, qty) ->
      let weight = Float.pow decay (Float.of_int i) in
      Decimal.(qty * of_float weight)
    )
    |> Seq.fold_left Decimal.( + ) Decimal.zero
  in
  let bid_weighted = weighted_sum t.bids in
  let ask_weighted = weighted_sum t.asks in
  let total = Decimal.(bid_weighted + ask_weighted) in
  if Decimal.is_zero total then None
  else Some Decimal.((bid_weighted - ask_weighted) / total)

(** Get total bid depth *)
let bid_depth t =
  PriceMap.fold (fun _ qty acc -> Decimal.(acc + qty)) t.bids Decimal.zero

(** Get total ask depth *)
let ask_depth t =
  PriceMap.fold (fun _ qty acc -> Decimal.(acc + qty)) t.asks Decimal.zero

(** Calculate volume-weighted average price for a given size *)
let vwap side size t =
  let levels = match side with
    | Buy -> PriceMap.to_seq t.asks  (* Buying from asks *)
    | Sell -> PriceMap.to_seq t.bids (* Selling to bids *)
  in
  let rec calculate remaining_size total_cost seq =
    if Decimal.(remaining_size <= zero) then
      Some Decimal.(total_cost / size)
    else
      match Seq.uncons seq with
      | None -> None  (* Not enough liquidity *)
      | Some ((price, qty), rest) ->
        let fill_qty = if Decimal.(qty > remaining_size) then remaining_size else qty in
        let cost = Decimal.(fill_qty * price) in
        calculate
          Decimal.(remaining_size - fill_qty)
          Decimal.(total_cost + cost)
          rest
  in
  calculate size Decimal.zero levels

(** Estimate slippage for a market order *)
let estimate_slippage side size t =
  match vwap side size t, mid_price t with
  | Some avg_price, Some mid when not (Decimal.is_zero mid) ->
    let slippage = match side with
      | Buy -> Decimal.((avg_price - mid) / mid)
      | Sell -> Decimal.((mid - avg_price) / mid)
    in
    Some Decimal.(slippage * of_float 10000.0)  (* In bps *)
  | _ -> None

(** Convert to orderbook_state for serialization *)
let to_state t : orderbook_state =
  let bids = PriceMap.bindings t.bids
    |> List.map (fun (price, quantity) -> { price; quantity }) in
  let asks = PriceMap.bindings t.asks
    |> List.map (fun (price, quantity) -> { price; quantity }) in
  {
    symbol = t.symbol;
    timestamp = t.timestamp;
    last_update_id = t.last_update_id;
    bids;
    asks;
    mid_price = mid_price t;
    spread_bps = spread_bps t;
    imbalance = imbalance t;
    weighted_imbalance = weighted_imbalance t;
  }
