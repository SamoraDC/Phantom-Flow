(** Risk Gateway - Main Executable

    This is the main entry point for the OCaml risk engine.
    It listens for order requests, validates them against risk rules,
    and responds with approval or rejection.
*)

open Lwt.Infix
open Types
open Risk

(** Server configuration *)
let port = try int_of_string (Sys.getenv "RISK_GATEWAY_PORT") with _ -> 8081
let max_position = try float_of_string (Sys.getenv "RISK_MAX_POSITION") with _ -> 1.0
let max_drawdown = try float_of_string (Sys.getenv "RISK_MAX_DRAWDOWN") with _ -> 0.05

(** Global state *)
let risk_engine = ref (Risk.create ~config:{
  Risk.default_config with
  max_position_size = Decimal.of_float max_position;
  max_drawdown_pct = max_drawdown;
} ())

let account = ref {
  balance = Decimal.of_float 10000.0;
  equity = Decimal.of_float 10000.0;
  positions = [];
  initial_balance = Decimal.of_float 10000.0;
  created_at = Unix.gettimeofday ();
}

let positions : (string, position) Hashtbl.t = Hashtbl.create 10

(** JSON response helpers *)
let json_response status body =
  let headers = Cohttp.Header.of_list [
    ("Content-Type", "application/json");
    ("Access-Control-Allow-Origin", "*");
  ] in
  Cohttp_lwt_unix.Server.respond_string ~status ~headers ~body ()

let ok_json body = json_response `OK body
let bad_request_json body = json_response `Bad_request body

(** API Handlers *)
let handle_health_check () =
  let response = `Assoc [
    ("status", `String "healthy");
    ("component", `String "risk-gateway");
    ("timestamp", `Float (Unix.gettimeofday ()));
    ("circuit_breaker", `Bool (Risk.is_circuit_breaker_active !risk_engine));
  ] in
  ok_json (Yojson.Safe.to_string response)

let handle_check_order body =
  try
    let json = Yojson.Safe.from_string body in
    let symbol = Yojson.Safe.Util.(json |> member "symbol" |> to_string) in
    let side_str = Yojson.Safe.Util.(json |> member "side" |> to_string) in
    let quantity = Yojson.Safe.Util.(json |> member "quantity" |> to_float) in

    let side = if side_str = "buy" then Buy else Sell in
    let order = {
      id = OrderId.generate ();
      symbol = Symbol.of_string symbol;
      side;
      order_type = Market;
      quantity = Decimal.of_float quantity;
      time_in_force = GTC;
      status = Pending;
      created_at = Unix.gettimeofday ();
      updated_at = Unix.gettimeofday ();
    } in

    let current_pos = match Hashtbl.find_opt positions symbol with
      | Some p -> p.quantity
      | None -> Decimal.zero
    in

    let result = Risk.check_order
      ~order
      ~account:!account
      ~positions:!account.positions
      ~current_position:current_pos
      !risk_engine
    in

    let response = match result with
      | Approved ->
        risk_engine := Risk.update_rate_limit !risk_engine;
        `Assoc [
          ("approved", `Bool true);
          ("order_id", `String order.id);
        ]
      | Rejected reason ->
        `Assoc [
          ("approved", `Bool false);
          ("reason", `String reason);
        ]
      | RequiresAdjustment { original; adjusted; reason } ->
        `Assoc [
          ("approved", `Bool true);
          ("adjusted", `Bool true);
          ("original_qty", `Float (Decimal.to_float original));
          ("adjusted_qty", `Float (Decimal.to_float adjusted));
          ("reason", `String reason);
          ("order_id", `String order.id);
        ]
    in
    ok_json (Yojson.Safe.to_string response)
  with e ->
    bad_request_json (Printf.sprintf {|{"error": "%s"}|} (Printexc.to_string e))

let handle_update_account body =
  try
    let json = Yojson.Safe.from_string body in
    let balance = Yojson.Safe.Util.(json |> member "balance" |> to_float) in
    let equity = Yojson.Safe.Util.(json |> member "equity" |> to_float) in

    account := { !account with
      balance = Decimal.of_float balance;
      equity = Decimal.of_float equity;
    };

    ok_json {|{"success": true}|}
  with e ->
    bad_request_json (Printf.sprintf {|{"error": "%s"}|} (Printexc.to_string e))

let handle_update_position body =
  try
    let json = Yojson.Safe.from_string body in
    let symbol = Yojson.Safe.Util.(json |> member "symbol" |> to_string) in
    let quantity = Yojson.Safe.Util.(json |> member "quantity" |> to_float) in
    let entry_price = Yojson.Safe.Util.(json |> member "entry_price" |> to_float) in

    let pos = {
      symbol = Symbol.of_string symbol;
      quantity = Decimal.of_float quantity;
      entry_price = Decimal.of_float entry_price;
      unrealized_pnl = Decimal.zero;
      realized_pnl = Decimal.zero;
      updated_at = Unix.gettimeofday ();
    } in

    Hashtbl.replace positions symbol pos;
    ok_json {|{"success": true}|}
  with e ->
    bad_request_json (Printf.sprintf {|{"error": "%s"}|} (Printexc.to_string e))

let handle_circuit_breaker body =
  try
    let json = Yojson.Safe.from_string body in
    let active = Yojson.Safe.Util.(json |> member "active" |> to_bool) in
    let reason = Yojson.Safe.Util.(json |> member "reason" |> to_string_option) in

    risk_engine := if active then
      Risk.activate_circuit_breaker (Option.value reason ~default:"manual") !risk_engine
    else
      Risk.deactivate_circuit_breaker !risk_engine;

    ok_json {|{"success": true}|}
  with e ->
    bad_request_json (Printf.sprintf {|{"error": "%s"}|} (Printexc.to_string e))

let handle_max_size body =
  try
    let json = Yojson.Safe.from_string body in
    let symbol = Yojson.Safe.Util.(json |> member "symbol" |> to_string) in
    let side_str = Yojson.Safe.Util.(json |> member "side" |> to_string) in
    let side = if side_str = "buy" then Buy else Sell in

    let current_pos = match Hashtbl.find_opt positions symbol with
      | Some p -> p.quantity
      | None -> Decimal.zero
    in

    let max_size = Risk.max_safe_order_size
      ~symbol
      ~side
      ~account:!account
      ~current_position:current_pos
      !risk_engine
    in

    let response = `Assoc [
      ("symbol", `String symbol);
      ("side", `String side_str);
      ("max_size", `Float (Decimal.to_float max_size));
    ] in
    ok_json (Yojson.Safe.to_string response)
  with e ->
    bad_request_json (Printf.sprintf {|{"error": "%s"}|} (Printexc.to_string e))

(** Request router *)
let router req body =
  let uri = Cohttp.Request.uri req in
  let meth = Cohttp.Request.meth req in
  let path = Uri.path uri in

  match (meth, path) with
  | `GET, "/health" -> handle_health_check ()
  | `POST, "/check-order" -> handle_check_order body
  | `POST, "/update-account" -> handle_update_account body
  | `POST, "/update-position" -> handle_update_position body
  | `POST, "/circuit-breaker" -> handle_circuit_breaker body
  | `POST, "/max-size" -> handle_max_size body
  | _ ->
    json_response `Not_found {|{"error": "Not found"}|}

(** Main server *)
let server =
  let callback _conn req body =
    Cohttp_lwt.Body.to_string body >>= fun body_str ->
    router req body_str
  in
  Cohttp_lwt_unix.Server.create
    ~mode:(`TCP (`Port port))
    (Cohttp_lwt_unix.Server.make ~callback ())

let () =
  Printf.printf "Starting Risk Gateway on port %d\n%!" port;
  Printf.printf "  Max position size: %.4f\n%!" max_position;
  Printf.printf "  Max drawdown: %.2f%%\n%!" (max_drawdown *. 100.0);
  Lwt_main.run server
