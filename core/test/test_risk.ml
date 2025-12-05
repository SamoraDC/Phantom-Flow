(** Tests for Risk Engine *)

open Types
open Risk

let test_position_limit () =
  let config = { default_config with max_position_size = Decimal.of_float 1.0 } in
  let result = check_position_size
    ~symbol:"BTCUSDT"
    ~current_position:Decimal.zero
    ~order_qty:(Decimal.of_float 0.5)
    ~order_side:Buy
    config
  in
  Alcotest.(check bool) "should approve" true (result = Approved)

let test_position_limit_exceeded () =
  let config = { default_config with max_position_size = Decimal.of_float 1.0 } in
  let result = check_position_size
    ~symbol:"BTCUSDT"
    ~current_position:(Decimal.of_float 0.8)
    ~order_qty:(Decimal.of_float 0.5)
    ~order_side:Buy
    config
  in
  match result with
  | RequiresAdjustment _ -> Alcotest.(check bool) "should require adjustment" true true
  | _ -> Alcotest.fail "Expected RequiresAdjustment"

let test_circuit_breaker () =
  let engine = create () in
  Alcotest.(check bool) "circuit breaker initially inactive" false
    (is_circuit_breaker_active engine);
  let engine = activate_circuit_breaker "test" engine in
  Alcotest.(check bool) "circuit breaker active after activation" true
    (is_circuit_breaker_active engine);
  let engine = deactivate_circuit_breaker engine in
  Alcotest.(check bool) "circuit breaker inactive after deactivation" false
    (is_circuit_breaker_active engine)

let test_rate_limit () =
  let config = { default_config with max_orders_per_minute = 2 } in
  let engine = create ~config () in
  Alcotest.(check bool) "first order allowed" true (check_rate_limit engine = Approved);
  let engine = update_rate_limit engine in
  let engine = update_rate_limit engine in
  match check_rate_limit engine with
  | Rejected _ -> Alcotest.(check bool) "third order rejected" true true
  | _ -> Alcotest.fail "Expected Rejected"

let () =
  let open Alcotest in
  run "Risk Engine" [
    "position_limits", [
      test_case "approve within limit" `Quick test_position_limit;
      test_case "adjust when exceeding limit" `Quick test_position_limit_exceeded;
    ];
    "circuit_breaker", [
      test_case "activation and deactivation" `Quick test_circuit_breaker;
    ];
    "rate_limit", [
      test_case "enforce rate limit" `Quick test_rate_limit;
    ];
  ]
